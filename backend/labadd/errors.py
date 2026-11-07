"""API error types with stable error codes (see docs/API.md)."""

from __future__ import annotations


class ApiError(Exception):
    status = 400
    code = "bad_request"
    message = "The request could not be processed."

    def __init__(self, code: str | None = None, message: str | None = None, status: int | None = None):
        super().__init__(message or self.message)
        if code:
            self.code = code
        if message:
            self.message = message
        if status:
            self.status = status


class Unauthenticated(ApiError):
    status = 401
    code = "unauthenticated"
    message = "Sign in to continue."


class Forbidden(ApiError):
    status = 403
    code = "forbidden"
    message = "You do not have permission to do that."


class NotFound(ApiError):
    # Uniform absence: never reveal whether an out-of-scope resource exists.
    status = 404
    code = "not_found"
    message = "Not found."


class Conflict(ApiError):
    status = 409
    code = "conflict"
    message = "The request conflicts with the current state."


class Invalid(ApiError):
    status = 422
    code = "invalid"
    message = "Some fields are invalid."


class TooMany(ApiError):
    status = 429
    code = "rate_limited"
    message = "Too many attempts. Wait a few minutes and try again."
