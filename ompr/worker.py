from abc import ABC, abstractmethod
import logging
import os
from pypaq.mpython.mptools import QMessage, Que, ExProcess
import signal
from typing import Any

from ompr.helpers import OMPRException

logger = logging.getLogger(__name__)


class RunningWorker(ABC):
    """ Worker for tasks,
    processes task given with kwargs and returns result.
    To be implemented by user """

    def __init__(self, **kwargs):
        self.n_task_ok = 0
        self.n_task_crashed = 0

    @abstractmethod
    def process(self, **kwargs) -> Any: pass


class RWW(ExProcess):
    """ RunningWorkerWrap (RWW) wraps RunningWorker object with ExProcess """

    def __init__(
            self,
            rww_class: type[RunningWorker],
            rww_init_kwargs: dict,
            sync_que: Que,
            **kwargs):
        super().__init__(**kwargs)
        self.rww_class = rww_class
        self.rww_init_kwargs = rww_init_kwargs
        self.sync_que = sync_que
        logger.info(f'> *** RWW *** id: {self.name} initialized')

    def exprocess_method(self):
        """ here, in a loop RWW tasks will be processed """

        def handler_timeout(signum, frame):
            raise OMPRException('RWW timeout')

        logger.info(f'> {self.name} pid: {os.getpid()} inits RunningWorker')
        rwo = self.rww_class(**self.rww_init_kwargs)
        logger.info(f'> {self.name} starts process loop ..')

        # attach the handler to the signal.SIGALRM
        signal.signal(signal.SIGALRM, handler_timeout)

        while True:
            ompr_msg = self.ique.get()
            assert ompr_msg is not None
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
                        signal.setitimer(signal.ITIMER_REAL, timeout)

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
                        signal.setitimer(signal.ITIMER_REAL, 0)

                    self.oque.put(QMessage(
                        type=   'RWW_exception' if type(result) is OMPRException else 'RWW_result',
                        data=   {
                            'rww_name': self.name,
                            'task_ix':  task_ix,
                            'task':     task,
                            'result':   result}))

        logger.info(f'> {self.name} finished process loop, n_task_ok:{rwo.n_task_ok}, n_task_crashed:{rwo.n_task_crashed}')