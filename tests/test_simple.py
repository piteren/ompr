import random
import time
import unittest

from ompr.simple import simple_process


class Test_simple(unittest.TestCase):

    def test_simple_process(self):

        def func(a:float, b:float) -> float:
            time.sleep(1)
            return a*b

        num_tasks = 20

        tasks = [{'a':random.random(), 'b':random.random()} for _ in range(num_tasks)]

        res = simple_process(
            tasks=          tasks,
            function=       func,
            loglevel=       10,
            num_workers=    4)
        print(len(res))
        self.assertTrue(len(res)==num_tasks)