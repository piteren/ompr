from typing import List, Dict, Callable, Any, Optional

from ompr.runner import RunningWorker, OMPRunner


def simple_process(
        tasks: List[Dict],                  # tasks to process, list of task kwargs
        function: Callable,                 # function that processes tasks
        num_workers: int=               4,
        rww_lifetime: Optional[int]=    None,
        rww_init_sync: bool=            False,
        rerun_crashed: bool=            True,
        log_rww_exception: bool=        True,
        logger=                         None,
        loglevel=                       30,
        **kwargs,
) -> List[Any]:
    """ base (blocking) function to process tasks using OMPR on CPUs """

    class SimpleRW(RunningWorker):
        def process(self, **kw) -> Any:
            return function(**kw)

    ompr = OMPRunner(
        rww_class=              SimpleRW,
        rww_lifetime=           rww_lifetime,
        rww_init_sync=          rww_init_sync,
        devices=                [None] * num_workers,
        rerun_crashed=          rerun_crashed,
        log_rww_exception=      log_rww_exception,
        raise_rww_exception=    False,
        logger=                 logger,
        loglevel=               loglevel,
        **kwargs)

    ompr.process(tasks)
    results = ompr.get_all_results()
    ompr.exit()
    return results
