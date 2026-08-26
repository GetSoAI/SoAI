"""SoAI - Updater API client for talking to the running SoAI service [backend/app/updater/api_client.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import getpass
import os
import ssl
from typing import TYPE_CHECKING
from urllib import parse, request

import httpx2

from app.updater.dependencies import UpdaterApiClientDependencies
from app.updater.networking import open_url
from core.auth.cookies import resolve_webui_cookie_names
from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.errors.exception_logging import log_exception, log_handled_exception
from core.errors.exceptions import ConfigurationError, ValidationError
from core.network.http_json import read_http_json_dict
from core.network.urls import build_host_port_url
from core.runtime.instance_record import read_verified_runtime_instance_record
from core.serialization.json import serialize_json_compact_stable_strict
from core.system_api.route_paths import SOAI_WEBUI_AUTH_LOGIN_PATH
from features.api.middleware import tls

if TYPE_CHECKING:
    from core.types.json import JSONDict

__all__ = ("UpdaterApiClient",)

OPERATION = "application_updater.prepare_ssl_context"
OPERATION_API_REQUEST = "application_updater.api_request"


class UpdaterApiClient:
    def __init__(self, deps: UpdaterApiClientDependencies) -> None:
        self._logger = deps.logger
        self._module_dependencies = deps.module_dependencies
        self._config = deps.config
        self._base_path = deps.base_path
        self._args = deps.args
        self._edition = deps.edition
        self._session_cookie: str | None = None
        self._password_cache: str | None = None

    def _is_tls_configured(self) -> bool:
        tls_enabled = self._module_dependencies.coerce_bool_with_default(
            self._config.get("SERVER.HTTP.SSL.TLS_ENABLED"),
            default=False,
            strict=False,
        )
        if tls_enabled:
            return True
        cert = str(self._config.get("SERVER.HTTP.SSL.CERT_FILE") or "").strip()
        key = str(self._config.get("SERVER.HTTP.SSL.KEY_FILE") or "").strip()
        return bool(cert and key)

    def _prepare_ssl_context(self, tls_enabled: bool) -> ssl.SSLContext | None:
        if not tls_enabled:
            return None
        context = ssl.create_default_context()
        ca_file = self._config.get("SERVER.HTTP.SSL.CA_FILE")
        if ca_file:
            try:
                context.load_verify_locations(cafile=str(ca_file))
            except OSError as exception:
                log_exception(
                    self._logger,
                    exception,
                    message="Failed to load custom CA file",
                    operation=OPERATION,
                    details={"ca_file": str(ca_file)},
                )
                raise ConfigurationError(
                    f"Failed to load custom CA file: {exception}",
                    operation="application_updater.prepare_ssl_context",
                    details={"ca_file": str(ca_file)},
                    cause=exception,
                ) from exception
        else:
            cert_file = str(self._config.get("SERVER.HTTP.SSL.CERT_FILE") or "").strip()
            key_file = str(self._config.get("SERVER.HTTP.SSL.KEY_FILE") or "").strip()
            tls_enabled_flag = self._module_dependencies.coerce_bool_with_default(
                self._config.get("SERVER.HTTP.SSL.TLS_ENABLED"),
                default=False,
                strict=False,
            )
            if tls_enabled_flag and (not cert_file and not key_file):
                tls_options, _is_user_supplied = tls.prepare_tls_configuration(self._config)
                auto_cert_file = tls_options.get("ssl_certfile")
                if not auto_cert_file:
                    raise ConfigurationError(
                        "TLS is enabled but no certificate was resolved for API verification.",
                    )
                context.load_verify_locations(cafile=str(auto_cert_file))
        return context

    def _resolve_login_password(self) -> str:
        if self._password_cache is not None:
            return self._password_cache
        env_password = os.environ.get("SOAI_UPDATER_PASSWORD", "")
        if isinstance(env_password, str) and env_password:
            self._password_cache = env_password
            return env_password
        if self._args.password_stdin:
            password = input()
            if not password:
                raise ValidationError("Updater stdin password cannot be empty.")
            self._password_cache = password
            return password
        if not self._args.silent:
            password = getpass.getpass("SoAI password: ")
            if not password:
                raise ValidationError("Updater password cannot be empty.")
            self._password_cache = password
            return password
        raise ValidationError(
            "Protected updater API calls require SOAI_UPDATER_PASSWORD, --password-stdin, or interactive mode.",
        )

    def _authenticate_session(
        self,
        *,
        base_url: str,
        timeout: float,
        ssl_context: ssl.SSLContext | None,
    ) -> dict[str, str]:
        username = self._args.username
        cookie_name = resolve_webui_cookie_names(parse.urlsplit(base_url).scheme).auth
        if username is None:
            return {}
        if self._session_cookie is not None:
            return {"Cookie": f"{cookie_name}={self._session_cookie}"}
        payload = {"username": username, "password": self._resolve_login_password()}
        request_obj = request.Request(
            f"{base_url}{SOAI_WEBUI_AUTH_LOGIN_PATH}",
            method="POST",
            headers={"Content-Type": "application/json"},
            data=serialize_json_compact_stable_strict(payload).encode("utf-8"),
        )
        with open_url(
            request_obj,
            timeout=timeout,
            context=ssl_context,
            offline_mode=True,
        ) as response:
            if response.status_code != 200:
                self._logger.warning(
                    "Updater WebUI login failed with status %s for user %s.",
                    response.status_code,
                    username,
                )
                return {}
            session_cookie = response.cookies.get(cookie_name)
            if not isinstance(session_cookie, str) or not session_cookie:
                self._logger.warning("Updater WebUI login succeeded but no session cookie was set.")
                return {}
            self._session_cookie = session_cookie
            return {"Cookie": f"{cookie_name}={session_cookie}"}

    def get_base_url_and_auth_headers(
        self,
        *,
        timeout: float,
    ) -> tuple[str, dict[str, str], ssl.SSLContext | None]:
        host = self._config.require_str("SERVER.HTTP.NETWORK.HOST")
        if self._args.port is not None:
            port = int(self._args.port)
            tls_enabled = self._is_tls_configured()
            scheme = "https" if tls_enabled else "http"
        else:
            runtime_record = read_verified_runtime_instance_record(
                resolve_runtime_record_path(self._base_path, logger=self._logger),
                base_dir=self._base_path,
                expected_edition=self._edition,
            )
            if runtime_record is None or runtime_record.api_endpoint is None:
                raise ValidationError(
                    "The running SoAI instance has not published an API endpoint.",
                )
            runtime_api_endpoint = runtime_record.api_endpoint
            host = runtime_api_endpoint.local_connect_host
            port = runtime_api_endpoint.effective_port
            scheme = runtime_api_endpoint.scheme
            tls_enabled = scheme == "https"
        ssl_context = self._prepare_ssl_context(tls_enabled)
        base_url = build_host_port_url(scheme, host, port)
        headers = self._authenticate_session(
            base_url=base_url,
            timeout=timeout,
            ssl_context=ssl_context,
        )
        return (base_url, headers, ssl_context)

    def make_api_request(
        self,
        *,
        method: str,
        url: str,
        timeout: float,
        headers: dict[str, str] | None = None,
        body: JSONDict | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> JSONDict | None:
        request_headers = dict(headers or {})
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        data = serialize_json_compact_stable_strict(body).encode("utf-8") if body else None
        request_obj = request.Request(url, method=method, headers=request_headers, data=data)
        try:
            with open_url(
                request_obj,
                timeout=timeout,
                context=ssl_context,
                offline_mode=True,
            ) as response:
                if response.status_code in (200, 201):
                    return read_http_json_dict(response, field="updater API response")
                self._logger.warning(
                    "API request to %s failed with status %s",
                    url,
                    response.status_code,
                )
        except ValidationError as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="Rejected updater API request due to invalid URL or JSON response.",
                operation=OPERATION_API_REQUEST,
                details={"url": url},
            )
        except httpx2.HTTPError as exception:
            log_handled_exception(
                self._logger,
                exception,
                message="HTTP error during updater API request.",
                operation=OPERATION_API_REQUEST,
                details={"url": url},
                level="debug",
            )
        return None
