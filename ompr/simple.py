from collections.abc import Callable
from typing import Any

from ompr.runner import RunningWorker, OMPRunner


def simple_process(
        tasks: list[dict],
        function: Callable,
        num_workers: int = 4,
        rww_lifetime: int | None = None,
        rww_init_sync: bool = False,
        rerun_crashed: bool = True,
        log_rww_exception: bool = True,
        loglevel: int = 30,
        **kwargs,
) -> list[Any]:
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
        loglevel=               loglevel,
        **kwargs)

    ompr.process(tasks)
    results = ompr.get_all_results()
    ompr.exit()
    return results