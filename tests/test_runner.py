import random
import time
import unittest

from ompr.runner import OMPRunner, RunningWorker, OMPRException

TESTS_LOGLEVEL = 20


# basic RunningWorker with random exception
class BRW(RunningWorker):
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


class TestOMPR(unittest.TestCase):

    def test_OMPR_base(self):

        n_tasks =   100
        workers =   10
        min_time =  1.1
        max_time =  1.9

        expected_run_time = (max_time + min_time) / 2 * n_tasks / workers

        ompr = OMPRunner(
            rww_class=      BRW,
            devices=        [None] * workers,
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(n_tasks)]

        s_time = time.time()

        ompr.process(tasks)
        results = ompr.get_all_results()

        run_time = time.time()-s_time
        print(f'done, expected run time: {expected_run_time:.1f}s')
        print(f'run time: {run_time:.1f}s ({len(results)})')

        self.assertTrue(isinstance(results[0], str))
        self.assertEqual(len(tasks), len(results))
        self.assertTrue(run_time < expected_run_time * 2)

        results = ompr.get_all_results()
        self.assertTrue(results == [])

        ompr.exit()

    def test_OMPR_put_one_by_one(self):

        n_tasks =   100
        workers =   10
        min_time =  1.1
        max_time =  1.9

        expected_run_time = (max_time + min_time) / 2 * n_tasks / workers

        ompr = OMPRunner(
            rww_class=      BRW,
            devices=        [None] * workers,
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(n_tasks)]

        s_time = time.time()

        for t in tasks:
            ompr.process(t)
        results = ompr.get_all_results()

        run_time = time.time() - s_time
        print(f'done, expected run time: {expected_run_time:.1f}s')
        print(f'run time: {run_time:.1f}s ({len(results)}) {results}')

        self.assertTrue(isinstance(results[0], str))
        self.assertEqual(len(tasks), len(results))
        self.assertTrue(run_time < expected_run_time * 2)

        results = ompr.get_all_results()
        self.assertTrue(results == [])

        ompr.exit()

    # results received one by one
    def test_OMPR_get_one_by_one(self):

        n_tasks =   50
        workers =   10
        min_time =  0.5
        max_time =  1.7

        ompr = OMPRunner(
            rww_class=      BRW,
            devices=        [None] * workers,
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(n_tasks)]

        ompr.process(tasks)
        results = []
        while len(results) < n_tasks:
            print(f'got {len(results)} results')
            results.append(ompr.get_result())

        self.assertTrue(isinstance(results[0], str))
        self.assertEqual(len(tasks), len(results))

        # check sorted
        prev = -1
        for res in results:
            curr = int(res.split('_')[0])
            self.assertTrue(curr > prev)
            prev = curr

        result = ompr.get_result(block=False)
        self.assertTrue(result is None)

        ompr.exit()

    # not sorted results
    def test_OMPR_one_by_one_not_sorted(self):

        n_tasks =   50
        workers =   10
        min_time =  0.5
        max_time =  1.7

        ompr = OMPRunner(
            rww_class=          BRW,
            devices=            [None] * workers,
            ordered_results=    False,
            report_delay=       2,
            loglevel=           TESTS_LOGLEVEL)

        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(n_tasks)]

        ompr.process(tasks)
        results = []
        while len(results) < n_tasks:
            print(f'got {len(results)} results')
            results.append(ompr.get_result())

        self.assertTrue(isinstance(results[0], str))
        self.assertEqual(len(tasks), len(results))

        result = ompr.get_result(block=False)
        self.assertTrue(result is None)

        ompr.exit()

    # process lifetime
    def test_OMPR_lifetime(self):

        n_tasks =           100
        workers =           10
        min_time =          0.5
        max_time =          1.7
        process_lifetime =  2

        ompr = OMPRunner(
            rww_class=      BRW,
            rww_lifetime=   process_lifetime,
            devices=        [None] * workers,
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(n_tasks)]

        ompr.process(tasks)
        results = ompr.get_all_results()
        print(f'results: ({len(results)}) {results}')
        self.assertTrue(isinstance(results[0], str))
        self.assertEqual(len(tasks), len(results))

        # additional 30 tasks
        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(30)]

        ompr.process(tasks)
        results = ompr.get_all_results()
        print(f'results: ({len(results)}) {results}')
        self.assertTrue(isinstance(results[0], str))
        self.assertEqual(len(tasks), len(results))

        ompr.exit()

    # exceptions
    def test_OMPR_exceptions(self):

        n_tasks =       100
        workers =       10
        min_time =      0.5
        max_time =      1.7
        exception_prob= 0.3

        ompr = OMPRunner(
            rww_class=      BRW,
            devices=        [None] * workers,
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{
            'ix':               ix,
            'min_time':         min_time,
            'max_time':         max_time,
            'exception_prob':   exception_prob}
            for ix in range(n_tasks)]

        ompr.process(tasks)
        results = ompr.get_all_results()
        for r in results:
            self.assertTrue(isinstance(r,str) or isinstance(r,OMPRException))
        self.assertEqual(len(tasks), len(results))

        # additional 30 tasks
        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(30)]

        ompr.process(tasks)
        results = ompr.get_all_results()
        for r in results:
            self.assertTrue(isinstance(r,str) or isinstance(r,OMPRException))
        self.assertEqual(len(tasks), len(results))

        ompr.exit()

    # task timeout
    def test_OMPR_timeout(self):

        n_tasks =       100
        workers =       10
        min_time =      0.5
        max_time =      1.7
        task_timeout =  1

        ompr = OMPRunner(
            rww_class=      BRW,
            devices=        [None] * workers,
            task_timeout=   task_timeout,
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{
            'ix':       ix,
            'min_time': min_time,
            'max_time': max_time}
            for ix in range(n_tasks)]
        ompr.process(tasks)
        results = ompr.get_all_results()
        self.assertEqual(len(tasks), len(results))
        ompr.exit()

    # lifetime + exceptions + timeout
    def test_OMPR_all_together(self):

        n_tasks =           100
        workers =           10
        min_time =          0.5
        max_time =          1.2
        exception_prob =    0.3
        task_timeout =      1
        process_lifetime =  2

        ompr = OMPRunner(
            rww_class=      BRW,
            rww_lifetime=   process_lifetime,
            devices=        [None] * workers,
            task_timeout=   task_timeout,
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{
            'ix':               ix,
            'min_time':         min_time,
            'max_time':         max_time,
            'exception_prob':   exception_prob}
            for ix in range(n_tasks)]
        ompr.process(tasks)
        results = ompr.get_all_results()
        self.assertEqual(len(tasks), len(results))
        ompr.exit()

    # many timeouts
    def test_OMPR_many_timeouts(self):

        n_tasks =           100
        min_time =          0.9
        max_time =          1.5
        exception_prob =    0.2
        task_timeout =      1

        ompr = OMPRunner(
            rww_class=          BRW,
            devices=            'all',
            task_timeout=       task_timeout,
            log_rww_exception=  False,
            report_delay=       2,
            loglevel=           TESTS_LOGLEVEL)

        tasks = [{
            'ix':               ix,
            'min_time':         min_time,
            'max_time':         max_time,
            'exception_prob':   exception_prob}
            for ix in range(n_tasks)]
        ompr.process(tasks)
        results = ompr.get_all_results()
        self.assertEqual(len(tasks), len(results))
        ompr.exit()

    # many fast tasks
    def test_OMPR_speed(self):

        # Fast RunningWorker
        class FRW(RunningWorker):
            def process(self, ix: int) -> int:
                return ix

        n_tasks =           100000

        ompr = OMPRunner(
            rww_class=      FRW,
            devices=        'all',
            report_delay=   2,
            loglevel=       TESTS_LOGLEVEL)

        tasks = [{'ix':ix} for ix in range(n_tasks)]
        ompr.process(tasks)
        results = ompr.get_all_results()
        self.assertEqual(len(tasks), len(results))
        ompr.exit()