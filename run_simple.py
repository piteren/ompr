import random
import time
from ompr.runner import OMPRunner, RunningWorker

TESTS_LOGLEVEL = 20


class BRW(RunningWorker):
    """basic RunningWorker with random exception"""
    def process(
            self,
            ix: int,
            min_time: float,
            max_time: float,
            exception_prob: float=  0.0) -> object:

        if random.random() < exception_prob:
            raise Exception('RandomlyCrashed')

        _sleep = min_time + random.random() * (max_time-min_time)
        time.sleep(_sleep)

        return f'{ix}_{_sleep}'

n_tasks = 50
workers = 10
min_time = 0.2
max_time = 0.4

expected_run_time = (max_time + min_time) / 2 * n_tasks / workers

ompr = OMPRunner(
    rww_class=BRW,
    devices=[None] * workers,
    report_delay=2,
    loglevel=TESTS_LOGLEVEL)

tasks = [{
    'ix': ix,
    'min_time': min_time,
    'max_time': max_time}
    for ix in range(n_tasks)]

s_time = time.time()

ompr.process(tasks)
results = ompr.get_all_results()

run_time = time.time() - s_time
print(f'done, expected run time: {expected_run_time:.1f}s')
print(f'run time: {run_time:.1f}s ({len(results)})')

assert isinstance(results[0], str)
assert len(tasks) == len(results)
assert run_time < expected_run_time * 2

results = ompr.get_all_results()
assert results == []

ompr.exit()