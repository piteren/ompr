from typing import Optional, Dict


# OMPR Exception, also returned when task raises any exception while processed by RW
class OMPRException(Exception):

    def __init__(self, *args, task:Optional[Dict]=None):
        self.task = task
        super().__init__(*args)