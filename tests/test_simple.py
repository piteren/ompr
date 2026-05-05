import random
import time

from ompr.simple import simple_process


def test_simple_process():

    def func(a:float, b:float) -> float:
        time.sleep(0.2)
        return a*b

    num_tasks = 20

    tasks = [{'a':random.random(), 'b':random.random()} for _ in range(num_tasks)]

    res = simple_process(
        tasks=          tasks,
        function=       func,
        num_workers=    4)
    print(f"got results: {len(res)}")
    assert len(res) == num_tasks
