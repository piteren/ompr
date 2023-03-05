![](ompr.png)

## OMPR - Object based Multi-Processing Runner

**OMPR** is a simple tool for processing tasks with object based subprocesses.

**OMPR** may be used for parallel processing of any type of tasks.
Usually a task means a function with given set of parameters. This function needs to be run (processed) to get
a return value - result.<br> There are also scenarios when for processing of given tasks an (big) object is needed.
The problem arises when time taken by object `__init__` is much higher than time taken by pure processing.
Example of such task is sentence parsing using SpaCy model.
**OMPR** allows to init such an object once in each subprocess while forking.

---
#### Setup

To run **OMPR** you will need to:
- Define a class that inherits from `RunningWorker`. Object of that class will be built in each subprocess.
`RunningWorker` must implement `process(**kwargs)` method that is responsible for processing given task and returning
its result. Task parameters and arguments are given with kwargs (dict) and result may be Any type.
- Build `OMPRunner`, give while init:
  - `RunningWorker` type
  - devices (GPU / CPU) to use
  - optionally define some advanced parameters of `OMPRunner`
- Give to `OMPRunner` tasks as a list of dicts with `process()` method. You may give any number of tasks at
any time. This method is non-blocking. It just gets the tasks and sends for processing immediately.

`OMPRunner` processes given tasks with `InternalProcessor` (IP) that guarantees non-blocking interface of `OMPRunner`.
Results may be received with two get methods (single or all) and by default will be ordered with tasks order.
Finally, `OMPRunner` needs to be closed with `exit()`.

This package also delivers `simple_process()` function for simple tasks processing, when *object* is not needed.<br>
You can check `/examples` for sample run code.

If you got any questions or need any support, please contact me:  me@piotniewinski.com

---
#### More about `RunningWorker`

There are two policies (managed by OMPR, controlled with `rw_lifetime` parameter) of `RunningWorker` lifecycle:
    
    1st - RunningWorker is closed after processing some task (1..N)
    2nd - RunningWorker is closed only when crashes or with the OMP exit

Each policy has job specific pros and cons. By default, second is activated with `rw_lifetime=None`.
    
    + all RunningWorkers are initialized once while OMP inits - it saves a time
    - memory kept by the RunningWorker may grow with the time (while processing many tasks)