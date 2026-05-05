# OMPR Exception, also returned when task raises any exception while processed by RW
class OMPRException(Exception):

    def __init__(self, *args, task: dict | None = None):
        self.task = task
        super().__init__(*args)