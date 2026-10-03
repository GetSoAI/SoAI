"""SoAI - Published release note history for update checks [backend/app/updater/release_history.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2

from app.updater.release_gateway import SOAI_GITHUB_RELEASES_API_URL
from core.concurrency.deadlines import deadline_after
from core.errors.exception_logging import log_handled_exception
from core.errors.exceptions import SoAIError, ValidationError
from core.meta.versioning import extract_release_version, parse_semantic_version
from core.network.http_json import read_http_json_value
from core.network.outbound_http_profiles import build_github_api_headers
from core.timing.constants import BACKGROUND_TIMEOUT_SEC

if TYPE_CHECKING:
    from core.logging.protocols import LoggerProtocol
    from core.types.json import JSONDict

__all__ = ("fetch_release_history_async",)

RELEASES_PER_PAGE = 100
MAX_RELEASE_PAGES = 100
OPERATION = "app.updater.release_history.fetch"


def _release_note_entry(release: JSONDict, version: str) -> JSONDict | None:
    body = release.get("body")
    if body is None or body == "":
        return None
    if not isinstance(body, str):
        raise ValidationError("GitHub release notes body must be text.")
    if not body.strip():
        return None
    return {
        "version": version,
        "body": body,
        "published_at": release.get("published_at"),
    }


async def fetch_release_history_async(
    http_client: httpx2.AsyncClient,
    *,
    timeout: float,
    current_version: str,
    latest_release: JSONDict,
    logger: LoggerProtocol,
    github_token: str | None = None,
) -> tuple[list[JSONDict], bool]:
    current = parse_semantic_version(current_version)
    latest_version = extract_release_version(latest_release)
    latest = parse_semantic_version(latest_version)
    if latest <= current:
        return ([], True)
    entries: dict[str, JSONDict] = {}
    complete = False
    invalid_entry: Exception | None = None
    latest_entry = None
    try:
        if latest_release.get("draft") is not True and latest_release.get("prerelease") is not True:
            latest_entry = _release_note_entry(latest_release, latest_version)
    except (SoAIError, ValueError, TypeError) as exception:
        invalid_entry = exception
    if latest_entry is not None:
        entries[latest_version] = latest_entry
    missing_notes: set[str] = {latest_version} if latest_entry is None else set()
    deadline = deadline_after(BACKGROUND_TIMEOUT_SEC)
    try:
        for page in range(1, MAX_RELEASE_PAGES + 1):
            remaining_seconds = deadline.remaining_seconds()
            if remaining_seconds <= 0:
                break
            response = await http_client.get(
                SOAI_GITHUB_RELEASES_API_URL,
                params={"per_page": RELEASES_PER_PAGE, "page": page},
                headers=build_github_api_headers(github_token=github_token),
                follow_redirects=False,
                timeout=min(float(timeout), remaining_seconds),
            )
            if response.status_code != 200:
                response.raise_for_status()
                raise ValidationError("GitHub release history must use HTTP 200.")
            payload = read_http_json_value(response, field="GitHub release history")
            if not isinstance(payload, list):
                raise ValidationError("GitHub release history must be a JSON array.")
            for item in payload:
                try:
                    if not isinstance(item, dict):
                        raise ValidationError("GitHub release history contains an invalid entry.")
                    if item.get("draft") is True or item.get("prerelease") is True:
                        continue
                    version = extract_release_version(item)
                    parsed = parse_semantic_version(version)
                    if not current < parsed <= latest:
                        continue
                    entry = _release_note_entry(item, version)
                    if entry is None:
                        missing_notes.add(version)
                        continue
                except (SoAIError, ValueError, TypeError) as exception:
                    if invalid_entry is None:
                        invalid_entry = exception
                    continue
                if version not in entries:
                    entries[version] = entry
                missing_notes.discard(version)
            if len(payload) < RELEASES_PER_PAGE:
                complete = invalid_entry is None and not missing_notes.difference(entries)
                break
    except (
        SoAIError,
        httpx2.RequestError,
        httpx2.HTTPStatusError,
        ValueError,
        TypeError,
    ) as exception:
        log_handled_exception(
            logger,
            exception,
            message="Release history was incomplete.",
            operation=OPERATION,
            level="warning",
        )
    if invalid_entry is not None:
        log_handled_exception(
            logger,
            invalid_entry,
            message="A release history entry was invalid.",
            operation=OPERATION,
            level="warning",
        )
    ordered = sorted(entries, key=parse_semantic_version, reverse=True)
    return ([entries[version] for version in ordered], complete)
