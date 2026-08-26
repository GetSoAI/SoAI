"""SoAI - Plugin download execution with cancellation and disk checks [backend/plugins/state/download_execution.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from core.concurrency.cancellation import TaskCancelledError
from core.concurrency.cancellation_cleanup import uncancel_then_cleanup
from core.concurrency.context import require_context_cancellation_id
from core.errors.exceptions import (
    InsufficientDiskSpaceError,
    NotFoundError,
    SecurityError,
    StateError,
    ValidationError,
)
from core.files.move_errors import DestinationExistsError
from core.files.move_with_cancellation import (
    MoveFileCommittedAfterCancellationError,
    move_file_with_cancellation,
)
from core.files.operations import async_remove_if_exists
from core.files.temp_files import create_secure_temp_file_descriptor
from core.filesystem.async_queries import async_path_exists
from core.hardware.reservation_claims import claim_reserved_write
from core.network.errors import (
    HTTPDownloadInsecureSchemeError,
    HTTPDownloadRedirectError,
    HTTPDownloadTooManyRedirectsError,
    NetworkPolicyDeniedError,
)
from core.network.http_download import download_http_stream_to_file
from core.network.policy import enforce_url_network_policy
from core.plugins.errors import PluginIncompatibleError
from core.plugins.file_suffixes import PLUGIN_FILE_SUFFIX
from core.runtime.network_policy import OfflineModeError, require_online_mode
from core.runtime.request_context import RequestContext
from plugins.action_response import (
    PluginActionResponse,
    accepted_plugin_action_response,
    insufficient_disk_space_response,
    network_policy_violation_response,
)
from plugins.package_audit import audit_plugin_package
from plugins.state.download_online_mode import (
    build_plugin_download_offline_mode_response,
    require_plugin_download_online_mode,
)
from plugins.state.download_request_validation import (
    PluginDownloadPreparation,
    build_download_metadata,
)

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.tasks.protocols import CancellationTokenScopeCallable
    from core.types.protocols import HttpClientProtocol
    from plugins.protocols_internal.runtime.internal_protocols import (
        PluginDownloadManagerProtocol,
    )

__all__ = ("execute_plugin_download",)

PLUGIN_DOWNLOAD_AUDIT_EXCEPTIONS = (
    NotFoundError,
    PluginIncompatibleError,
    SecurityError,
    StateError,
    ValidationError,
)


def _accepted_plugin_download_response(
    prep: PluginDownloadPreparation,
) -> PluginActionResponse:
    return accepted_plugin_action_response(
        {
            "status": "accepted",
            "plugin_name": prep.plugin_name,
            "message": (
                f"Plugin '{prep.plugin_name}' downloaded successfully. "
                "It will be loaded shortly."
            ),
        },
    )


async def execute_plugin_download(
    *,
    manager: PluginDownloadManagerProtocol,
    prep: PluginDownloadPreparation,
    temp_directory: str,
    cancellation_token_scope: CancellationTokenScopeCallable,
    logger: LoggerProtocol,
    context: RequestContext | None,
    http_client: HttpClientProtocol,
    on_progress: Callable[[int, int | None, float, float], Awaitable[None] | None] | None = None,
) -> PluginActionResponse:
    if not manager.state.configuration.downloads_enabled:
        return PluginActionResponse(
            success=False,
            status_code=403,
            error_type="downloads_disabled",
            error_message="Plugin downloads are disabled by the administrator.",
        )
    runtime_flags = manager.dependencies.infrastructure.runtime_flags
    offline_error = require_plugin_download_online_mode(runtime_flags)
    if offline_error is not None:
        return offline_error
    lifecycle = manager.dependencies.infrastructure.lifecycle
    temp_file_path: str | None = None
    try:
        async with lifecycle.plugin_lock_scope(prep.plugin_name):
            if await async_path_exists(prep.final_path):
                return PluginActionResponse(
                    success=False,
                    status_code=409,
                    error_type="conflict",
                    error_message=f"Plugin file '{prep.filename}' already exists.",
                )
            cancellation_id = require_context_cancellation_id(context)
            metadata = build_download_metadata(prep.filename, prep.plugin_name)
            async with cancellation_token_scope(
                lifecycle.token_collection,
                lifecycle.cancellation_history,
                lifecycle.cancellation_event_bus,
                cancellation_id=cancellation_id,
                owner="plugin_download",
                metadata=metadata,
                logger=logger,
            ) as token:
                storage_manager = manager.dependencies.infrastructure.storage_manager

                async def download_url_validator(check_url: str) -> str | None:
                    require_online_mode(runtime_flags, source="plugin_download")
                    return await enforce_url_network_policy(
                        check_url,
                        block_private_networks=prep.network_policy_enabled,
                        dns_timeout_sec=prep.dns_timeout_sec,
                        source="plugin_download",
                    )

                file_descriptor, temp_file_path = create_secure_temp_file_descriptor(
                    directory=temp_directory,
                    prefix="soai-",
                    suffix=PLUGIN_FILE_SUFFIX,
                )
                os.close(file_descriptor)
                download_result = await download_http_stream_to_file(
                    http_client=http_client,
                    url=prep.url,
                    destination_path=temp_file_path,
                    cancellation_token=token,
                    max_bytes=None,
                    max_redirects=10,
                    allow_http_scheme=prep.allow_insecure_downloads,
                    timeout_seconds=300.0,
                    url_validator=download_url_validator,
                    on_progress=on_progress,
                    reservation_provider=storage_manager,
                    reservation_path=temp_file_path,
                    reservation_operation="plugin_state.download_package.download",
                    reservation_details={
                        "purpose": "plugin_download_temp_file",
                        "temp_directory": temp_directory,
                    },
                )
                try:
                    await audit_plugin_package(
                        manager,
                        prep.plugin_name,
                        file_path_override=temp_file_path,
                        enforce_import_scan=True,
                        enforce_hash_policy=True,
                    )
                except PLUGIN_DOWNLOAD_AUDIT_EXCEPTIONS as exception:
                    if isinstance(exception, PluginIncompatibleError):
                        return PluginActionResponse(
                            success=False,
                            status_code=409,
                            error_type="conflict",
                            error_message=exception.compatibility.message,
                        )
                    return PluginActionResponse(
                        success=False,
                        status_code=400,
                        error_type="invalid_plugin",
                        error_message=str(exception),
                    )
                with storage_manager.reserve_disk_space(
                    path=prep.final_path,
                    required_bytes=download_result.bytes_written,
                    operation="plugin_state.download_package.install",
                    details={
                        "purpose": "plugin_download_install_volume",
                        "final_path": prep.final_path,
                        "downloaded_bytes": download_result.bytes_written,
                    },
                ) as install_reservation:
                    with claim_reserved_write(
                        install_reservation,
                        size_bytes=download_result.bytes_written,
                    ):
                        await move_file_with_cancellation(
                            temp_file_path,
                            prep.final_path,
                            token,
                            allow_overwrite=False,
                        )
                    temp_file_path = None
        return _accepted_plugin_download_response(prep)
    except InsufficientDiskSpaceError as exception:
        return insufficient_disk_space_response(exception)
    except MoveFileCommittedAfterCancellationError:
        return _accepted_plugin_download_response(prep)
    except TaskCancelledError:
        return PluginActionResponse(
            success=False,
            status_code=499,
            error_type="cancelled",
            error_message="Plugin download was cancelled.",
        )
    except OfflineModeError as exception:
        return build_plugin_download_offline_mode_response(exception)
    except DestinationExistsError:
        return PluginActionResponse(
            success=False,
            status_code=409,
            error_type="conflict",
            error_message=f"Plugin file '{prep.filename}' already exists.",
        )
    except HTTPDownloadTooManyRedirectsError as exception:
        return PluginActionResponse(
            success=False,
            status_code=502,
            error_type="too_many_redirects",
            error_message=str(exception),
        )
    except HTTPDownloadInsecureSchemeError as exception:
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="insecure_url",
            error_message=str(exception),
        )
    except HTTPDownloadRedirectError as exception:
        return PluginActionResponse(
            success=False,
            status_code=502,
            error_type="redirect_error",
            error_message=str(exception),
        )
    except NetworkPolicyDeniedError as exception:
        return network_policy_violation_response(exception)
    except ValidationError as exception:
        return PluginActionResponse(
            success=False,
            status_code=400,
            error_type="invalid_url",
            error_message=str(exception),
        )
    finally:
        if temp_file_path:
            temp_file_cleanup = async_remove_if_exists(
                temp_file_path,
                logger=logger,
                log_level=logging.DEBUG,
            )
            await uncancel_then_cleanup(temp_file_cleanup)
