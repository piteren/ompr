import random
import time

from ompr.simple import simple_process


# function processing tasks
def func(a:float, b:float) -> float:
    time.sleep(1)
    return a*b


if __name__ == "__main__":

    tasks = [{'a':random.random(), 'b':random.random()} for _ in range(100)] # prepare tasks

    # process tasks and get results
    res = simple_process(
        tasks=          tasks,
        function=       func,
        num_workers=    4,
        report_delay=   5,
        loglevel=       20)

    print(len(res))
    print(res)