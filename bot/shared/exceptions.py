class MementoError(Exception):
    """Base domain exception."""


class TaskNotFoundError(MementoError):
    pass


class UserNotFoundError(MementoError):
    pass


class DeadlineParseError(MementoError):
    pass


class DeadlineTooSoonError(MementoError):
    pass


class OutcomeAlreadyRecordedError(MementoError):
    pass


class UnauthorizedError(MementoError):
    pass


class WorkerNotRegisteredError(MementoError):
    pass
