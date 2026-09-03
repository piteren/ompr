from collections.abc import Callable
from typing import Any

from ompr import RunningWorker, OMPRunner


def simple_process(
        tasks: list[dict],
        function: Callable,
        **kwargs,
) -> list[Any]:
    """ base (blocking) function to process tasks using OMPR on CPUs
    example:
        results_list = simple_process(
            tasks=[{'file':f} for f in files],
            function=get_file_somthing,
            report_interval=60,
            loglevel_subproc=30,
            devices=0.95)
    """

    class SimpleRW(RunningWorker):
        def process(self, **kw) -> Any:
            return function(**kw)

    ompr = OMPRunner(rww_class=SimpleRW, **kwargs)
    ompr.process(tasks)
    results = ompr.get_all_results()
    ompr.exit()
    return results