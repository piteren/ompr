'<!--SKIP_FIX-->'
![](ompr.png)

## OMPR - Object-based Multi-Processing Runner

**OMPR** is a simple tool for processing tasks with object-based subprocesses.

**OMPR** may be used for parallel processing of any type of tasks.
Usually, a task means a function with a given set of parameters. This function needs to be run (processed) to get
a return value - result. There are also scenarios when for processing a given task a (big) object is needed.
The problem arises when the time taken by object `__init__` is much higher than the time taken by pure processing.
An example of such a task is sentence parsing using a SpaCy model.
**OMPR** allows initializing such an object once in each subprocess while forking.

---
#### Setup

To run **OMPR**, you will need to:
- Define a class that inherits from `RunningWorker`. An object of that class will be built in each subprocess.
`RunningWorker` must implement the `process(**kwargs)` method that is responsible for processing a given task and returning
its result. Task parameters and arguments are given with kwargs (dict), and the result may be of any type.
- Build `OMPRunner`, giving during initialization:
  - `RunningWorker` type
  - Devices (GPU / CPU) to use
  - Optionally define some advanced parameters of `OMPRunner`
- Give to `OMPRunner` tasks as a list of dicts with the `process()` method. You may give any number of tasks at
any time. This method is non-blocking. It just gets the tasks and sends them for processing immediately.

`OMPRunner` processes given tasks with `InternalProcessor` (IP) that guarantees a non-blocking interface of `OMPRunner`.
Results may be received with two get methods (single or all) and by default will be ordered according to the tasks' order.
Finally, `OMPRunner` needs to be closed with `exit()`.

This package also delivers the `simple_process()` function for simple tasks processing when an *object* is not needed.
You can check `/examples` for sample run code.

If you have any questions or need any support, please contact me: me@piotniewinski.com

---
#### More about `RunningWorker`

There are two policies (managed by OMPR, controlled with the `rww_lifetime` parameter) of `RunningWorker` lifecycle:
    
    1st - RunningWorker is closed after processing some task (1..N)
    2nd - RunningWorker is closed only when it crashes or with the OMP exit

Each policy has job-specific pros and cons. By default, the second is activated with `rww_lifetime=None`.
    
    + all RunningWorkers are initialized once while OMP inits - it saves time
    - memory kept by the RunningWorker may grow over time (while processing many tasks)