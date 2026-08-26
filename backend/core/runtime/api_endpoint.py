"""SoAI - Authoritative runtime API endpoint contract [backend/core/runtime/api_endpoint.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass

from core.errors.exceptions import ValidationError
from core.network.hosts import normalize_host
from core.types.json import JSONDict

__all__ = ("RuntimeApiEndpoint",)


@dataclass(frozen=True, slots=True)
class RuntimeApiEndpoint:
    bind_host: str
    scheme: str
    preferred_port: int
    effective_port: int

    def __post_init__(self) -> None:
        normalized_host = normalize_host(self.bind_host)
        if normalized_host is None:
            raise ValidationError("Runtime API bind host is required.")
        if self.bind_host.strip() != self.bind_host or not self.bind_host:
            raise ValidationError("Runtime API bind host must be normalized.")
        if self.scheme not in {"http", "https"}:
            raise ValidationError("Runtime API scheme must be 'http' or 'https'.")
        self._validate_port(self.preferred_port, field="preferred_port")
        self._validate_port(self.effective_port, field="effective_port")

    @property
    def local_connect_host(self) -> str:
        normalized_host = normalize_host(self.bind_host)
        if normalized_host == "0.0.0.0":
            return "127.0.0.1"
        if normalized_host == "::":
            return "::1"
        return self.bind_host

    @property
    def fallback_active(self) -> bool:
        return self.effective_port != self.preferred_port

    def local_connection_coordinates(self) -> tuple[str, str, int]:
        return self.scheme, self.local_connect_host, self.effective_port

    def to_public_payload(self) -> JSONDict:
        return {
            "scheme": self.scheme,
            "port": self.effective_port,
            "preferred_port": self.preferred_port,
            "fallback_active": self.fallback_active,
        }

    def to_record_payload(self) -> JSONDict:
        return {
            "bind_host": self.bind_host,
            "scheme": self.scheme,
            "preferred_port": self.preferred_port,
            "effective_port": self.effective_port,
        }

    @classmethod
    def from_record_payload(cls, payload: JSONDict) -> RuntimeApiEndpoint:
        expected_fields = {
            "bind_host",
            "scheme",
            "preferred_port",
            "effective_port",
        }
        if set(payload) != expected_fields:
            raise ValidationError("Runtime API endpoint fields are invalid.")
        bind_host = payload["bind_host"]
        scheme = payload["scheme"]
        preferred_port = payload["preferred_port"]
        effective_port = payload["effective_port"]
        if not isinstance(bind_host, str) or not isinstance(scheme, str):
            raise ValidationError("Runtime API endpoint host and scheme must be strings.")
        if (
            not isinstance(preferred_port, int)
            or isinstance(preferred_port, bool)
            or not isinstance(effective_port, int)
            or isinstance(effective_port, bool)
        ):
            raise ValidationError("Runtime API endpoint ports must be integers.")
        return cls(
            bind_host=bind_host,
            scheme=scheme,
            preferred_port=preferred_port,
            effective_port=effective_port,
        )

    @staticmethod
    def _validate_port(value: int, *, field: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool) or value not in range(1, 65536):
            raise ValidationError(f"Runtime API {field} must be an integer from 1 through 65535.")
