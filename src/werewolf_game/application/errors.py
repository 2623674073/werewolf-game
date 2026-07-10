class ApplicationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFoundError(ApplicationError):
    pass


class ConflictError(ApplicationError):
    pass


class CapacityError(ApplicationError):
    pass
