class MementoError(Exception):
    """Base domain exception."""


class TaskNotFoundError(MementoError):
    pass


class UserNotFoundError(MementoError):
    pass


class DeadlineParseError(MementoError):
    pass


class UnauthorizedError(MementoError):
    pass
