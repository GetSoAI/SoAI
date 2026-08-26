"""SoAI - External accounts service protocols [backend/core/external_accounts/protocols.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from core.concurrency.protocols import AsyncContextManagerProtocol

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

    from core.external_accounts.linked_account_definition import LinkedAccountDefinition
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = (
    "DatabaseExternalAccountsProtocol",
    "ExternalAccountsServiceProtocol",
    "LinkedAccountAuthorizationProtocol",
    "LinkedAccountCreationProtocol",
    "LinkedAccountMutationProtocol",
    "LinkedAccountPolicyProtocol",
    "LinkedAccountQueryProtocol",
    "LinkedDomainAccountStorageProtocol",
)


class DatabaseExternalAccountsProtocol(Protocol):
    @property
    def fernet(self) -> tuple[Fernet, ...]: ...

    async def list_accounts(
        self,
        *,
        user_id: int,
        decrypt_secrets: bool = False,
    ) -> list[JSONDict]: ...

    async def get_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        decrypt_secrets: bool = False,
    ) -> JSONDict | None: ...

    async def create_account(
        self,
        *,
        user_id: int,
        payload: JSONDict,
    ) -> JSONDict: ...

    async def update_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        updates: JSONDict,
    ) -> JSONDict | None: ...

    async def delete_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> bool: ...


class ExternalAccountsServiceProtocol(Protocol):
    def account_lock(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> AsyncContextManagerProtocol[None]: ...

    async def list_accounts(self, user_id: int) -> list[JSONDict]: ...

    async def get_account(
        self,
        user_id: int,
        external_account_id: str,
        *,
        decrypt_secrets: bool = False,
    ) -> JSONDict | None: ...

    async def create_account(
        self,
        *,
        user_id: int,
        payload: JSONDict,
    ) -> JSONDict: ...

    async def update_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        updates: JSONDict,
    ) -> JSONDict | None: ...

    async def delete_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> bool: ...

    async def start_oauth(
        self,
        *,
        user_id: int,
        external_account_id: str,
        resource: str,
    ) -> JSONDict: ...

    async def get_oauth_status(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> JSONDict: ...

    async def clear_oauth(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> JSONDict: ...

    async def complete_oauth_callback(
        self,
        *,
        code: str,
        state_token: str,
        user_id: int,
    ) -> JSONDict: ...

    async def get_access_token(
        self,
        *,
        user_id: int,
        external_account_id: str,
    ) -> JSONDict: ...

    def build_xoauth2_sasl(
        self,
        *,
        user_email: str,
        access_token: str,
    ) -> str: ...


class LinkedAccountCreationProtocol(Protocol):
    async def create_account(self, *, user_id: int, payload: JSONDict) -> JSONDict: ...


class LinkedAccountMutationProtocol(Protocol):
    async def update_account(
        self,
        *,
        user_id: int,
        account_id: str,
        payload: JSONDict,
    ) -> JSONDict | None: ...

    async def delete_account(self, *, user_id: int, account_id: str) -> bool: ...


class LinkedAccountQueryProtocol(Protocol):
    async def list_accounts(self, user_id: int) -> JSONDict: ...

    async def test_account(self, *, user_id: int, account_id: str) -> JSONDict: ...


class LinkedAccountAuthorizationProtocol(Protocol):
    async def start_oauth(
        self,
        *,
        user_id: int,
        account_id: str,
    ) -> JSONDict: ...

    async def get_oauth_status(self, *, user_id: int, account_id: str) -> JSONDict: ...

    async def clear_oauth(self, *, user_id: int, account_id: str) -> JSONDict: ...


class LinkedAccountPolicyProtocol(Protocol):
    @property
    def definition(self) -> LinkedAccountDefinition: ...

    @property
    def logger(self) -> LoggerProtocol: ...

    def extract_domain_payload(self, payload: JSONDict) -> JSONDict: ...

    def format_account(
        self,
        domain_account: JSONDict,
        external_account: JSONDict,
    ) -> JSONDict: ...

    async def validate_payload(self, *, user_id: int, payload: JSONDict) -> None: ...

    async def test_account(self, *, user_id: int, account_id: str) -> JSONDict: ...


class LinkedDomainAccountStorageProtocol(Protocol):
    async def list_accounts(self, *, user_id: int) -> list[JSONDict]: ...

    async def get_account(self, *, user_id: int, account_id: str) -> JSONDict | None: ...

    async def create_account(
        self,
        *,
        user_id: int,
        external_account_id: str,
        payload: JSONDict,
    ) -> JSONDict: ...

    async def update_account(
        self,
        *,
        user_id: int,
        account_id: str,
        updates: JSONDict,
    ) -> JSONDict | None: ...

    async def delete_account(self, *, user_id: int, account_id: str) -> bool: ...
