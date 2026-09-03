class AppError(Exception):
    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def not_found(detail: str = "Not Found") -> AppError:
    return AppError(404, detail)


def bad_request(detail: str) -> AppError:
    return AppError(400, detail)


def unauthorized(detail: str) -> AppError:
    return AppError(401, detail)


def forbidden(detail: str = "Forbidden") -> AppError:
    return AppError(403, detail)


def conflict(detail: str) -> AppError:
    return AppError(409, detail)
