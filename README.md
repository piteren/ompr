## ompr - Object based Multi-Processing Runner

    Tasks may be given for OMPRunner with process() method - one dict after another or in packages (List[dict]).
    Results may be received with two get methods (single or all) and by default will be ordered with tasks order.
    Result returned by RunningWorker may be Any type.
    OMPRunner needs to be closed with exit().

    OMPRunner processes given tasks with InternalProcessor (IP) that guarantees non-blocking interface of OMPRunner.
    Tasks are processed by RunningWorker class objects that are managed by IP (and additionally wrapped by RWW).

    RunningWorker must be inherited and its process() implemented.
    process() takes task via **kwargs and returns task result.
    There are two main policies of RunningWorker lifecycle:
        1st - RunningWorker is closed after processing some task (1 typically but may be N)
        2nd - RunningWorker is closed only when crashes or with the OMP exit
        Each policy has job specific pros and cons. By default, second is activated with 'rw_lifetime=None'.
        'rw_lifetime=None' has some pros and cons:
            + all RunningWorkers are initialized once while OMP inits - it saves a time
            - memory kept by the RunningWorker may grow with the time (while processing many tasks)
