from typing import List, Dict, Callable, Any

from ompr.runner import RunningWorker, OMPRunner


# base function to process tasks using OMPR
def simple_process(
        tasks: List[Dict],      # tasks to process
        function: Callable,     # processing function
        num_workers: int=   4,
        **kwargs,
) -> List[Any]:

    class SimpleRW(RunningWorker):
        def process(self, **kwargs) -> Any:
            return function(**kwargs)

    ompr = OMPRunner(
        rw_class=   SimpleRW,
        devices=    [None]*num_workers,
        **kwargs)

    ompr.process(tasks)
    results = ompr.get_all_results()
    ompr.exit()
    return results
