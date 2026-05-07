from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProviderErrorKind(str, Enum):
    NOT_CONFIGURED = 'not_configured'
    AUTH_ERROR = 'auth_error'
    RATE_LIMITED = 'rate_limited'
    TIMEOUT = 'timeout'
    NETWORK_ERROR = 'network_error'
    SERVER_ERROR = 'server_error'
    BAD_REQUEST = 'bad_request'
    NOT_FOUND = 'not_found'
    UNPROCESSABLE = 'unprocessable'
    BAD_RESPONSE = 'bad_response'
    UNKNOWN = 'unknown'


def kind_from_status_code(status_code: int | None) -> ProviderErrorKind:
    if status_code in {401, 403}:
        return ProviderErrorKind.AUTH_ERROR
    if status_code == 429:
        return ProviderErrorKind.RATE_LIMITED
    if status_code == 400:
        return ProviderErrorKind.BAD_REQUEST
    if status_code == 404:
        return ProviderErrorKind.NOT_FOUND
    if status_code == 422:
        return ProviderErrorKind.UNPROCESSABLE
    if status_code is not None and status_code >= 500:
        return ProviderErrorKind.SERVER_ERROR
    return ProviderErrorKind.UNKNOWN


def retryable(kind: ProviderErrorKind) -> bool:
    return kind in {
        ProviderErrorKind.RATE_LIMITED,
        ProviderErrorKind.TIMEOUT,
        ProviderErrorKind.NETWORK_ERROR,
        ProviderErrorKind.SERVER_ERROR,
        ProviderErrorKind.UNKNOWN,
    }


@dataclass(slots=True)
class ProviderCallError(Exception):
    message: str
    kind: ProviderErrorKind = ProviderErrorKind.UNKNOWN
    status_code: int | None = None
    provider_name: str | None = None
    retryable: bool | None = None

    def __post_init__(self) -> None:
        if self.retryable is None:
            self.retryable = retryable(self.kind)
        Exception.__init__(self, self.message)

    def to_metadata(self) -> dict[str, object | None]:
        return {
            'provider_error_kind': self.kind.value,
            'provider_status_code': self.status_code,
            'provider_retryable': self.retryable,
            'provider_name': self.provider_name,
            'message': self.message,
        }
