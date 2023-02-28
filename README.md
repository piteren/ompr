## OMPR - Object based Multi-Processing Runner

------------

**OMPR** is a simple framework that enables processing tasks with subprocesses.
Each subprocess will init an object of given class while forking the process. This object will be responsible for processing all task that will be sent to given subprocess with a queue.
**OMPR** may be used for parallel processing of any type of tasks, but *object* concept is extremely useful for processing small tasks with (big) objects, that need to be preloaded and time of task processing is relatively short
comparing to time of object init. Example of such task is sentence parsing using SpaCy model.



To run **OMPR** you will need to:
- Define a class that inherits from a **RunningWorker**. Object of that class will be built in each subprocess.
RunningWorker must implement process(**kwargs) method that is responsible for processing given task and returning
its result. Task parameters and arguments are given with kwargs (dict) and result may be Any type.
- Build an **OMPRunner** object, give while init:
  - RunningWorker type
  - devices (GPU / CPU) to use
  - optionally define some advanced parameters of OMPRunner
- Give to OMPRunner tasks as a list of dicts with OMPRunner.process() method. You may give any number of tasks at
any time. This method is non-blocking. It just gets the tasks and sends for processing immediately.

OMPRunner processes given tasks with InternalProcessor (IP) that guarantees non-blocking interface of OMPRunner.
Results may be received with two get methods (single or all) and by default will be ordered with tasks order.
Finally, OMPRunner needs to be closed with exit().

------------

There are two policies of RunningWorker lifecycle:
    
    1st - RunningWorker is closed after processing some task (1..N)
    2nd - RunningWorker is closed only when crashes or with the OMP exit

Each policy has job specific pros and cons. By default, second is activated with 'rw_lifetime=None'.
    
    + all RunningWorkers are initialized once while OMP inits - it saves a time
    - memory kept by the RunningWorker may grow with the time (while processing many tasks)

------------

This package also delivers `simple_process()` function for simple tasks processing, when *object* is not needed.

You can check `/tests` for some run examples.

If you got any questions or need any support, please contact me:  me@piotniewinski.com
