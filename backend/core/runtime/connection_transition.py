"""SoAI - Accepted API connection transition contract [backend/core/runtime/connection_transition.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.licensing.identifiers import require_canonical_uuid4
from core.oauth.management_urls import resolve_oauth_public_origin
from core.types.json import JSONDict
from core.validation.integers import is_positive_strict_int

__all__ = ("ConnectionTransition",)

if TYPE_CHECKING:
    from typing import Literal

    type ConnectionTransitionScheme = Literal["http", "https"]
    type ConnectionTransitionDestination = Literal["same_address", "public_origin", "manual"]

_SCHEMES: frozenset[str] = frozenset({"http", "https"})
_DESTINATIONS: frozenset[str] = frozenset({"same_address", "public_origin", "manual"})


@dataclass(frozen=True, slots=True)
class ConnectionTransition:
    configuration_revision: int
    instance_id: str
    current_scheme: ConnectionTransitionScheme
    requested_scheme: ConnectionTransitionScheme
    destination: ConnectionTransitionDestination
    public_origin: str | None = None

    def __post_init__(self) -> None:
        if not is_positive_strict_int(self.configuration_revision):
            raise ValidationError("Connection transition revision must be a positive integer.")
        require_canonical_uuid4(self.instance_id)
        if self.current_scheme not in _SCHEMES or self.requested_scheme not in _SCHEMES:
            raise ValidationError("Connection transition schemes must be 'http' or 'https'.")
        if self.destination not in _DESTINATIONS:
            raise ValidationError("Connection transition destination is invalid.")
        if (self.destination == "public_origin") != (self.public_origin is not None):
            raise ValidationError(
                "Connection transition public origin is required only for public-origin destinations.",
            )

        if self.public_origin is not None:
            resolve_oauth_public_origin(self.public_origin)

    def to_public_payload(self) -> JSONDict:
        return {
            "configuration_revision": self.configuration_revision,
            "instance_id": self.instance_id,
            "current_scheme": self.current_scheme,
            "requested_scheme": self.requested_scheme,
            "destination": self.destination,
            "public_origin": self.public_origin,
        }
