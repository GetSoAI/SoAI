"""SoAI - Installation-scoped CLI endpoint probing [backend/app/cli/instance_control_discovery.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from app.cli.instance_control_config import load_config_dict
from app.cli.instance_control_probes import probe_api_health, probe_api_reachable
from app.cli.offline_mode import resolve_config_path
from core.bootstrap.background_probe import (
    DiscoveryProbeResult,
    resolve_runtime_endpoint_probe,
)
from core.bootstrap.runtime_record_path import resolve_runtime_record_path
from core.config.value_validation import is_config_dict
from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger
from core.runtime.instance_record import read_verified_runtime_instance_record
from core.system_api.route_paths import SOAI_SYSTEM_HEALTH_PATH

__all__ = (
    "DiscoveryProbeResult",
    "probe_discovery",
    "probe_discovery_api_health",
    "probe_discovery_api_reachable",
)

LOGGER_NAME = "SoAI.app.cli.instance_control_discovery"
OPERATION = "app.cli.instance_control.probe_runtime_endpoint"
SYSTEM_HEALTH_CHECK_PATH = SOAI_SYSTEM_HEALTH_PATH


def _resolve_probe_ca_file(base_dir: str) -> str | None:
    loaded = load_config_dict(resolve_config_path(base_dir))
    if not is_config_dict(loaded):
        return None
    server_section = loaded.get("SERVER")
    system_api = server_section.get("HTTP") if is_config_dict(server_section) else None
    if not is_config_dict(system_api):
        return None
    ssl_section = system_api.get("SSL")
    if not is_config_dict(ssl_section):
        return None
    configured_ca_file = ssl_section.get("CA_FILE")
    if isinstance(configured_ca_file, str) and configured_ca_file.strip():
        return os.path.abspath(os.path.expanduser(configured_ca_file.strip()))
    configured_cert_file = ssl_section.get("CERT_FILE")
    if not isinstance(configured_cert_file, str) or not configured_cert_file.strip():
        return None
    cert_file = os.path.abspath(os.path.expanduser(configured_cert_file.strip()))
    local_ca_file = os.path.join(os.path.dirname(cert_file), "soai-local-root-ca.crt")
    return local_ca_file if os.path.isfile(local_ca_file) else None


def probe_discovery(
    base_dir: str,
    *,
    expected_edition: str,
) -> DiscoveryProbeResult | None:
    logger = get_logger(LOGGER_NAME)
    try:
        runtime_record = read_verified_runtime_instance_record(
            resolve_runtime_record_path(base_dir, logger=logger),
            base_dir=base_dir,
            expected_edition=expected_edition,
        )
        if runtime_record is None or runtime_record.api_endpoint is None:
            return None
        return resolve_runtime_endpoint_probe(
            runtime_record.api_endpoint,
            ca_file=_resolve_probe_ca_file(base_dir),
        )
    except RECOVERABLE_EXCEPTIONS as exception:
        log_handled_exception(
            logger,
            exception,
            message="Failed to resolve installation runtime endpoint.",
            operation=OPERATION,
            level="debug",
        )
        return None


def probe_discovery_api_reachable(discovery_info: DiscoveryProbeResult) -> bool:
    return probe_api_reachable(discovery_info.host, discovery_info.port)


def probe_discovery_api_health(discovery_info: DiscoveryProbeResult) -> bool:
    return probe_api_health(
        discovery_info.host,
        discovery_info.port,
        discovery_info.scheme,
        SYSTEM_HEALTH_CHECK_PATH,
        ca_file=discovery_info.ca_file,
    )
