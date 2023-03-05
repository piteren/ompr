from typing import List, Dict, Callable, Any

from ompr.runner import RunningWorker, OMPRunner


# base (blocking) function to process tasks using OMPR
def simple_process(
        tasks: List[Dict],      # tasks to process
        function: Callable,     # processing function
        num_workers: int=   4,
        logger=             None,
        loglevel=           30,
        **kwargs,
) -> List[Any]:

    class SimpleRW(RunningWorker):
        def process(self, **kw) -> Any:
            return function(**kw)

    ompr = OMPRunner(
        rw_class=   SimpleRW,
        devices=    [None]*num_workers,
        logger=     logger,
        loglevel=   loglevel,
        **kwargs)

    ompr.process(tasks)
    results = ompr.get_all_results()
    ompr.exit()
    return results
