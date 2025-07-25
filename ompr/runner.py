from abc import ABC, abstractmethod
from collections import deque
from inspect import getfullargspec
import os
import psutil
from pypaq.lipytools.moving_average import MovAvg
from pypaq.lipytools.pylogger import get_pylogger, get_child
from pypaq.pms.base import get_params
from pypaq.mpython.mptools import QMessage, Que, ExProcess
from pypaq.mpython.devices import DevicesPypaq, get_devices
import signal
import time
from typing import Any, List, Dict, Optional, Union

from ompr.helpers import OMPRException


class RunningWorker(ABC):
    """ Worker for tasks,
    processes task given with kwargs and returns result.
    To be implemented by user """

    def __init__(self):
        self.n_task_ok = 0
        self.n_task_crashed = 0

    @abstractmethod
    def process(self, **kwargs) -> Any: pass


class OMPRunner:
    """ Object based Multi-Processing Runner """

    class InternalProcessor(ExProcess):
        """ Internal Processor of OMPRunner
        manages RunningWorkers:
         - inits them, sends tasks, receives results
        it is designed as a subprocess of OMPRunner to not block OMPRunner (main) process """

        class RWW(ExProcess):
            """ RWW wraps RunningWorker object with ExProcess """

            def __init__(
                    self,
                    rww_class: type(RunningWorker),
                    rww_init_kwargs: Dict,
                    sync_que: Que,
                    **kwargs):
                super().__init__(**kwargs)
                self.rww_class = rww_class
                self.rww_init_kwargs = rww_init_kwargs
                self.sync_que = sync_que
                self.logger.info(f'> *** RWW *** id: {self.name} initialized')

            def exprocess_method(self):
                """ here, in a loop RWW tasks will be processed """

                def handler_timeout(signum, frame):
                    raise OMPRException('RWW timeout')

                self.logger.info(f'> {self.name} pid: {os.getpid()} inits RunningWorker')
                rwo = self.rww_class(**self.rww_init_kwargs)
                self.logger.info(f'> {self.name} starts process loop ..')

                # attach the handler to the signal.SIGALRM
                signal.signal(signal.SIGALRM, handler_timeout)

                while True:
                    ompr_msg: QMessage = self.ique.get()
                    if ompr_msg.type not in ['break','hold_check','task']:
                        raise OMPRException(f'RWW received unknown message: {ompr_msg.type}')

                    if ompr_msg.type == 'break':
                        break

                    if ompr_msg.type == 'hold_check':
                        self.sync_que.put(QMessage(type='hold_ready', data=None))

                    if ompr_msg.type == 'task':
                        task_ix = ompr_msg.data['task_ix']
                        timeout = ompr_msg.data['task_timeout']
                        task = ompr_msg.data['task']
                        result = None

                        # try block for timeout exception
                        try:

                            if timeout is not None:
                                signal.alarm(timeout)

                            try:
                                result = rwo.process(**task)
                                rwo.n_task_ok += 1
                            except Exception as e:
                                if self.raise_Exception:
                                    raise e
                                result = OMPRException(f'exception while processing task #{task_ix}: {e}', task=task)
                                rwo.n_task_crashed += 1

                        except Exception as e:
                            if self.raise_Exception:
                                raise e
                            result = OMPRException(f'exception while processing task #{task_ix}: {e}', task=task)
                            rwo.n_task_crashed += 1

                        finally:

                            # cancel the alarm
                            if timeout is not None:
                                signal.alarm(0)

                            self.oque.put(QMessage(
                                type=   'RWW_exception' if type(result) is OMPRException else 'RWW_result',
                                data=   {
                                    'rww_name': self.name,
                                    'task_ix':  task_ix,
                                    'task':     task,
                                    'result':   result}))

                self.logger.info(f'> {self.name} finished process loop, n_task_ok:{rwo.n_task_ok}, n_task_crashed:{rwo.n_task_crashed}')

        POISON_MSG = QMessage(type='poison', data=None) # to kill RWWs
        STOP_MSG = QMessage(type='stop', data=None) # to stop RWWs

        def __init__(
                self,
                rww_class: type(RunningWorker),
                rww_init_kwargs: Optional[Dict],
                rww_lifetime: Optional[int],
                rww_init_sync: bool,
                devices: DevicesPypaq,
                ordered_results: bool,
                task_timeout: Optional[int],
                rerun_crashed: bool,
                log_rww_exception: bool,
                raise_rww_exception: bool,
                report_delay: Optional[int],
                **kwargs):

            self.rww_class = rww_class
            super().__init__(
                name=               f'InternalProcessor_for_{self.rww_class.__name__}',
                raise_Exception=    raise_rww_exception,
                **kwargs)

            self.que_sync = Que() # this que is (optionally) used only to sync init of RWWs

            if not rww_init_kwargs: rww_init_kwargs = {}
            self.rww_lifetime = rww_lifetime
            self.rww_init_sync = rww_init_sync

            devices = get_devices(devices=devices)
            self.logger.info(f'> {self.name} resolved devices: {devices}')

            dev_param_name = None
            pms = getfullargspec(self.rww_class).args
            if 'devices' in pms: dev_param_name = 'devices'
            if 'device' in pms: dev_param_name = 'device'

            self.ordered_results = ordered_results
            self.task_timeout = task_timeout
            self.rerun_crashed = rerun_crashed
            self.log_rww_exception = log_rww_exception
            self.raise_rww_exception = raise_rww_exception
            self.report_delay = report_delay

            self.rwwD: Dict[str,Dict] = {}  # {rww.name: {rww_init_kwargs, rww, n_tasks}}
            for dix, dev in enumerate(devices):
                kwD = {}
                kwD.update(rww_init_kwargs)
                if dev_param_name:
                    kwD[dev_param_name] = dev
                self.rwwD[f'RWW-{dix}'] = {
                    'rww_init_kwargs':  kwD,    # kwargs of RWW __init__
                    'rww':              None,   # RWW object
                    'n_tasks':          0,      # number of tasks processed by each RWW since start / restart
                }

        def _build_and_start_RWW(self, rww_name:str):
            """ builds and starts single RWW """
            assert self.rwwD[rww_name]['rww'] is None
            self.rwwD[rww_name]['rww'] = OMPRunner.InternalProcessor.RWW(
                rww_class=          self.rww_class,
                rww_init_kwargs=    self.rwwD[rww_name]['rww_init_kwargs'],
                sync_que=           self.que_sync,
                ique=               Que(),
                oque=               self.ique,
                name=               rww_name,
                raise_Exception=    self.raise_rww_exception,
                logger=             get_child(logger=self.logger, name=rww_name, change_level=10))
            self.rwwD[rww_name]['rww'].start()
            self.rwwD[rww_name]['n_tasks'] = 0
            self.logger.debug(f'> {self.name} built and started {rww_name} ..')

        def build_and_start_allRWW(self):
            self.logger.info(f'> {self.name} is going to build and start {len(self.rwwD)} RunningWorkers ..')
            n_started = 0
            for id in self.rwwD:
                if self.rwwD[id]['rww'] is None:
                    self._build_and_start_RWW(id)
                    n_started += 1
            self.logger.info(f'> {self.name} built and started {n_started} RunningWorkers')
            if self.rww_init_sync:
                self._hold_till_allRWW_ready()
                self.logger.info(f'> {self.name} RunningWorkers init finished / synced')

        def _stop_and_join_RWW(self, name:str):
            """ ** not used currently by InternalProcessor
            stops and joins single RWW
            drawback is that it needs to wait till RWW eventually finishes current task """
            self.rwwD[name]['rww'].ique.put(QMessage('break'))
            self.rwwD[name]['rww'].join()
            self.rwwD[name]['rww'] = None
            self.logger.debug(f'> {self.name} stopped and joined {name} ..')

        def _stop_and_join_allRWW(self):
            self.logger.info(f'> {self.name} is going to stop and join {len(self.rwwD)} RunningWorkers ..')
            for name in self.rwwD:
                if self.rwwD[name]['rww'] is not None:
                    self._stop_and_join_RWW(name)
            self.logger.info(f'> {self.name} stopped and joined all RunningWorkers')

        def _kill_RWW(self, name:str):
            """ kills single RWW """

            self.rwwD[name]['rww'].kill()

            # flush the RWW ique
            while True:
                if not self.rwwD[name]['rww'].ique.get(block=False): 
                    break

            self.rwwD[name]['rww'].join()
            self.rwwD[name]['rww'] = None
            self.logger.debug(f'> {self.name} killed and joined {name} ..')

        def _kill_allRWW(self):
            self.logger.info(f'> {self.name} is going to kill and join {len(self.rwwD)} RunningWorkers ..')
            for name in self.rwwD:
                if self.rwwD[name]['rww'] is not None:
                    self._kill_RWW(name)
            self.logger.info(f'> {self.name} killed and joined all RunningWorkers')

        def _hold_till_allRWW_ready(self):
            """ holds execution (syncs) till all RWW finished init """
            for name in self.rwwD:
                if self.rwwD[name]['rww'] is None:
                    self.logger.warning('some RWW are not started, cannot hold!')
                    return
            for name in self.rwwD:
                self.rwwD[name]['rww'].ique.put(QMessage(type='hold_check', data=None))
            for _ in self.rwwD:
                self.que_sync.get()

        def _get_rww_info(self) -> str:
            """ returns information about subprocesses """

            ip_id = os.getpid()
            ip_mem = int(psutil.Process(ip_id).memory_info().rss / 1024 ** 2)
            vm = psutil.virtual_memory()
            used = vm.used / 1024 ** 3

            num_all = len(self.rwwD)
            num_alive = sum([1 for n in self.rwwD if self.rwwD[n]['rww'] is not None and self.rwwD[n]['rww'].alive])
            num_closed = sum([1 for n in self.rwwD if self.rwwD[n]['rww'] is not None and self.rwwD[n]['rww'].closed])
            alive_info = f'{num_all}= alive:{num_alive} closed:{num_closed}'

            rww_mem = [int(psutil.Process(self.rwwD[name]['rww'].pid).memory_info().rss / 1024 ** 2) for name in self.rwwD if self.rwwD[name]['rww'].alive]
            rww_mem.sort(reverse=True)

            tot_mem = ip_mem + sum(rww_mem)
            s = f'# {self.name} mem: {ip_mem}MB, omp+sp/used: {tot_mem/1024:.1f}/{used:.1f}GB ({int(vm.percent)}%VM) '
            if len(rww_mem) > 6: s += f'subproc: {rww_mem[:3]}-{int(sum(rww_mem)/len(rww_mem))}-{rww_mem[-3:]} ({alive_info})'
            else:                s += f'subproc: {rww_mem} ({alive_info})'
            return s

        def exprocess_method(self):
            """ main loop of InternalProcessor """

            self.logger.info(f'> {self.name} (pid: {os.getpid()}) starts loop with {len(self.rwwD)} RWW')
            self.build_and_start_allRWW()

            next_task_ix = 0                # next task index (index of task that will be processed next)
            task_result_ix = 0              # index of task result that should be put to self.results_que now

            s_time = time.time()            # start time
            iv_time = s_time                # interval report time
            iv_n_tasks = 0                  # number of tasks processed since last interval
            n_tasks_processed = 0           # total number of tasks processed
            speed_mavg = MovAvg(factor=0.2) # speed (tasks/min)

            # que of (task_ix, task) to be processed
            # here tasks are immediately rewritten after receiving with the self.ique
            tasks_que = deque()

            # list [RWW name] of all available (not busy) resources
            resources = list(self.rwwD.keys())

            # results dict {task_ix: result(data)}
            # this dict is used for ordering results according to tasks order
            resultsD: Dict[int, Any] = {}

            break_ompr = False
            while not break_ompr:

                msg_ique = self.ique.get() # wait for any message

                if msg_ique.type not in [
                    'poison',
                    'stop',
                    'tasks',
                    'RWW_result',
                    'RWW_exception',
                ]:
                    nfo = f'{self.name} received unknown message type: \'{msg_ique.type}\''
                    self.logger.error(nfo)
                    raise OMPRException(nfo)

                self.logger.debug(f'> {self.name} got \'{msg_ique.type}\' message from ique')

                if msg_ique.type == 'poison':
                    # all RWW have to be killed here
                    # we want to kill them because it is quicker than waiting for them till finish tasks
                    # - we do not need their results anymore
                    self._kill_allRWW()
                    break_ompr = True

                if msg_ique.type == 'stop':
                    # all RWW have to be stopped here
                    self._stop_and_join_allRWW()
                    break_ompr = True

                if msg_ique.type == 'tasks':
                    for task in msg_ique.data:
                        tasks_que.append((next_task_ix, task))
                        next_task_ix += 1

                if msg_ique.type in ['RWW_result','RWW_exception']:

                    rww_name = msg_ique.data['rww_name']
                    task_ix = msg_ique.data['task_ix']
                    task = msg_ique.data['task']
                    result = msg_ique.data['result']
                    self.logger.debug(f'> {self.name} got message from {rww_name} for task {task_ix}')

                    _send_result = True

                    if type(result) is OMPRException:

                        if self.log_rww_exception:
                            self.logger.warning(f'> {self.name} got exception message from {rww_name} for task #{task_ix}: {result}')

                        self.logger.debug(f'> restarting RWW: {rww_name} because crashed task:{task_ix} ..')
                        self._kill_RWW(rww_name)
                        self._build_and_start_RWW(rww_name)

                        if self.rerun_crashed:
                            tasks_que.appendleft((task_ix, task))
                            _send_result = False

                    if _send_result:

                        res_msg = QMessage(type='result', data=result)

                        if self.ordered_results:
                            resultsD[task_ix] = res_msg
                        else:
                            self.oque.put(res_msg)

                        if type(result) is not OMPRException:
                            self.rwwD[rww_name]['n_tasks'] += 1
                        n_tasks_processed += 1
                        iv_n_tasks += 1

                    resources.append(rww_name)

                    # flush resultsD
                    while task_result_ix in resultsD:
                        self.oque.put(resultsD.pop(task_result_ix))
                        task_result_ix += 1

                # eventually put resources + tasks into work
                while resources and tasks_que:

                    self.logger.debug(f'> free resources: {len(resources)}, tasks_que len: {len(tasks_que)}, ique.qsize: {self.ique.qsize}')

                    rww_name = resources.pop(0) # take first free resource

                    # eventually restart RWW because of lifetime condition
                    if self.rww_lifetime and self.rwwD[rww_name]['n_tasks'] >= self.rww_lifetime:
                        self.logger.debug(f'> restarting RWW: {rww_name} because of lifetime condition ..')
                        self._kill_RWW(rww_name)
                        self._build_and_start_RWW(rww_name)

                    # get first task, prepare and put message for RWW
                    task_ix, task = tasks_que.popleft()
                    msg = QMessage(
                        type=   'task',
                        data=   {
                            'task_ix':      task_ix,
                            'task_timeout': self.task_timeout,
                            'task':         task})
                    self.rwwD[rww_name]['rww'].ique.put(msg)

                    self.logger.debug(f'> put task {task_ix} for {rww_name}')

                # report time
                if self.report_delay is not None and time.time()-iv_time > self.report_delay:

                    iv_speed = iv_n_tasks/((time.time()-iv_time)/60)
                    speed_now = speed_mavg.upd(iv_speed)
                    speed_global = n_tasks_processed/((time.time()-s_time)/60)

                    if speed_now != 0:
                        if speed_now > 10:    speed_now_str = f'{int(speed_now)} tasks/min'
                        else:
                            if speed_now > 1: speed_now_str = f'{speed_now:.1f} tasks/min'
                            else:             speed_now_str = f'{1 / speed_now:.1f} min/task'
                        n_tasks_que = len(tasks_que)
                        est = n_tasks_que / speed_global
                        progress = n_tasks_processed / next_task_ix
                        self.logger.info(f'> progress: {progress * 100:4.1f}% ({speed_now_str}) que:{n_tasks_que}/{next_task_ix}, EST:{est:.1f}min')
                    else:
                        self.logger.info(f'> processing speed unknown yet ..')

                    iv_time = time.time()
                    iv_n_tasks = 0

                    self.logger.debug(self._get_rww_info())
                    self.logger.debug(f'RWW n_tasks:')
                    for rk in sorted(self.rwwD.keys()):
                        self.logger.debug(f'{rk:2}: {self.rwwD[rk]["n_tasks"]}')

        def after_exception_handle_run(self):
            self._kill_allRWW()
            self.logger.debug(f'> {self.name} killed all RWW after exception occurred')

        @property
        def num_RWW(self) -> int:
            return len(self.rwwD)

        def exit(self, kill:bool=True) -> None:
            """ method to call out of the process to exit InternalProcessor """

            if self.alive:
                self.ique.put(self.POISON_MSG if kill else self.STOP_MSG)

            if kill:
                # flush the oque
                while self.alive:
                    while True:
                        if self.oque.get(block=False) is None:
                            break

    def __init__(
            self,
            rww_class: type(RunningWorker),
            rww_init_kwargs: Optional[Dict]=    None,
            rww_lifetime: Optional[int]=        None,
            rww_init_sync: bool=                False,
            devices: DevicesPypaq=              'all',
            ordered_results: bool=              True,
            task_timeout: Optional[int]=        None,
            rerun_crashed: bool=                True,
            log_rww_exception: bool=            True,
            raise_rww_exception: bool=          False,
            report_delay: Union[int,str]=       'auto',
            logger=                             None,
            loglevel=                           20):
        """
        :param rww_class:
             RunningWorker class that will process() given tasks
        :param rww_init_kwargs:
            RunningWorker __init__ kwargs, logger is managed by OMPRunner
        :param rww_lifetime:
            RunningWorker lifetime,
            None or 0 - unlimited,
            N <1,n> - each RWW will be restarted after processing N tasks
        :param rww_init_sync:
            holds execution till all RWW finished init and are ready to process tasks,
            sometimes RWW init may take a lot of time and we want to sync their init
            to start task processing with all RWW at the same moment
        :param ordered_results:
            returns results in the order of tasks
        :param task_timeout:
            RWW process will be killed after that time (sec) of processing,
            when timeout happens OMPRException will be returned as a task result
        :param log_rww_exception:
            RWW exception is put to the logging with a WARNING
        :param raise_rww_exception:
            OMPR (in fact InternalProcessor) manages exceptions raised by RWW when processing the task,
            RWW are rebuild, crashed tasks are re-run,
            True forces RWW to raise exceptions (all but KeyboardInterrupt)
            this option is useful for debugging
        :param report_delay:
            num sec between speed_report,
            'auto' - uses loglevel,
            'none' - there is no speed report """

        if not logger:
            logger = get_pylogger(
                name=       self.__class__.__name__,
                folder=     None,
                level=      loglevel)
        self.logger = logger

        if self.logger.level < 20:
            log_rww_exception = True

        self.logger.info(f'*** OMPRunner *** inits, '
                         f'pid: {os.getpid()}, '
                         f'rww_class: {rww_class.__name__}')

        self._tasks_que = Que()             # que of tasks to be processed
        self._results_que = Que()           # que of ready results
        self._n_tasks_received: int = 0     # number of tasks received from user till now
        self._n_results_returned: int = 0   # number of results returned to user till now

        if report_delay == 'none':
            report_delay = None
        if report_delay == 'auto':
            report_delay = 30 if loglevel>10 else 10

        if not rww_init_kwargs:
            rww_init_kwargs = {}

        # eventually add self.logger to rww_init_kwargs
        rww_class_params = get_params(rww_class.__init__)
        if 'logger' in rww_class_params['with_defaults'] or 'logger' in rww_class_params['without_defaults']:
            rww_init_kwargs['logger'] = self.logger

        self._internal_processor = OMPRunner.InternalProcessor(
            ique=                   self._tasks_que,
            oque=                   self._results_que,
            rww_class=              rww_class,
            rww_init_kwargs=        rww_init_kwargs if rww_init_kwargs else {},
            rww_lifetime=           rww_lifetime,
            rww_init_sync=          rww_init_sync,
            devices=                devices,
            ordered_results=        ordered_results,
            task_timeout=           task_timeout,
            rerun_crashed=          rerun_crashed,
            log_rww_exception=      log_rww_exception,
            raise_rww_exception=    raise_rww_exception,
            report_delay=           report_delay,
            logger=                 self.logger)
        self._internal_processor.start()

    def process(self, tasks: dict or List[dict]):
        """ takes tasks for processing, (not blocking)
        starts processing, does not return anything """
        if type(tasks) is dict: tasks = [tasks]
        self._tasks_que.put(QMessage(type='tasks', data=tasks))
        self._n_tasks_received += len(tasks)

    def get_result(self, block=True) -> Optional[Any]:
        """ returns single result, may block or not """
        if self._n_results_returned == self._n_tasks_received:
            self.logger.info(f'OMPRunner get_result() returns None since already returned all results (for all given tasks: n_results_returned == n_tasks_received)')
            return None
        else:
            msg = self._results_que.get(block=block)
            if msg:
                self._n_results_returned += 1
                return msg.data
            return None

    def get_all_results(self, pop_ex_results=False) -> List[Any]:
        """ returns results of all tasks put up to NOW
        pop_ex_results for True removes OMPRException result from the returned list """
        results = []
        while self._n_tasks_received > self._n_results_returned:
            results.append(self.get_result(block=True))
        if pop_ex_results:
            results = [r for r in results if type(r) is not OMPRException]
        return results

    def get_tasks_stats(self) -> Dict[str,int]:
        return {
            'n_tasks_received':     self._n_tasks_received,
            'n_results_returned':   self._n_results_returned}

    def get_num_workers(self) -> int:
        return self._internal_processor.num_RWW

    def exit(self):
        kill = False
        if self._n_results_returned != self._n_tasks_received:
            kill = True
            self.logger.warning(f'{self.__class__.__name__} exits while not all results were returned to user!')
        self._internal_processor.exit(kill=kill)
        self._internal_processor.join()
        self.logger.info(f'> internal processor stopped, {self.__class__.__name__} exits.')