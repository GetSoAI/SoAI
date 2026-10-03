"""SoAI - HTTP artifact representation and replay state [backend/core/network/resumable_downloads.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping

import httpx2

from core.errors.exceptions import ValidationError
from core.network.errors import HTTPDownloadSizeLimitError
from core.network.http_download_metadata import (
    HTTPDownloadResponseMetadata,
    read_http_download_response_metadata,
    resolve_download_response_range,
)
from core.network.outbound_http_profiles import merge_outbound_headers
from core.network.transfer_retry import HTTPTransferAttempts, HTTPTransferRetryPolicy
from core.validation.strict_numbers import require_non_negative_int_strict

__all__ = ("DownloadStreamState", "DownloadReplayRequired")


class DownloadReplayRequired(ValidationError): ...


class DownloadStreamState:
    def __init__(
        self,
        *,
        url: str,
        policy: HTTPTransferRetryPolicy,
        timeout: float,
        headers: Mapping[str, str] | None,
        max_bytes: int | None,
        prefix_length: int = 0,
        prefix_sha256: str | None = None,
        metadata_reader: Callable[[Mapping[str, str]], HTTPDownloadResponseMetadata] | None = None,
    ) -> None:
        if max_bytes is not None:
            require_non_negative_int_strict(max_bytes, error_message="Invalid maximum size.")
        self.base_headers = merge_outbound_headers(headers or {}, {"Accept-Encoding": "identity"})
        if any(name.lower() in {"range", "if-range"} for name in self.base_headers):
            raise ValidationError("Range and If-Range are owned by the artifact stream.")
        self.attempts = HTTPTransferAttempts(policy, url=url)
        self.timeout = policy.bounded_timeout(timeout)
        self.closed = False
        self._entered = False
        self._iterated = False
        self.max_bytes = max_bytes
        self.metadata_reader = metadata_reader
        self.position = 0
        self.resumed_bytes = 0
        self.total_length: int | None = None
        self.content_type: str | None = None
        self.final_url = ""
        self._etag: str | None = None
        self._digest = hashlib.sha256()
        self._prefix_sha256: str | None = None
        self._persisted_unverified = False
        self._force_full = False
        self._requested_offset = 0
        self._response_length: int | None = None
        self._response_received = 0
        self._replay_remaining = 0
        self._replay_digest = hashlib.sha256()
        self.retain_prefix(prefix_length, prefix_sha256)

    def enter(self) -> None:
        if self._entered or self.closed:
            raise ValidationError("An artifact stream cannot be entered more than once.")
        self._entered = True

    def retain_prefix(self, length: int, sha256: str | None) -> None:
        if self._entered:
            raise ValidationError("Retained state must be supplied before the stream is opened.")
        require_non_negative_int_strict(length, error_message="Invalid retained length.")
        if self.max_bytes is not None and length > self.max_bytes:
            raise ValidationError("Retained download exceeds maximum size.")
        if length and (sha256 is None or re.fullmatch(r"[0-9a-f]{64}", sha256) is None):
            raise ValidationError("A retained download requires its SHA-256 digest.")
        self.position = length
        self.resumed_bytes = length
        self._prefix_sha256 = sha256
        self._persisted_unverified = length > 0
        self._force_full = length > 0

    def begin_iteration(self) -> None:
        if not self._entered or self.closed or self._iterated:
            raise ValidationError("An artifact stream requires one active consumer.")
        self._iterated = True

    @property
    def replay_pending(self) -> bool:
        return self._replay_remaining > 0

    def request_headers(self) -> dict[str, str]:
        self._requested_offset = 0
        if (
            self.position > 0
            and self._etag is not None
            and not self._force_full
            and (self.total_length is None or self.position < self.total_length)
        ):
            self._requested_offset = self.position
            return merge_outbound_headers(
                self.base_headers,
                {"Range": f"bytes={self.position}-", "If-Range": self._etag},
            )
        return dict(self.base_headers)

    def accept(self, response: httpx2.Response) -> None:
        headers = response.headers
        if headers.get("Content-Encoding", "identity").strip().lower() != "identity":
            raise ValidationError("Artifact responses must use identity Content-Encoding.")
        metadata = (
            self.metadata_reader(headers)
            if self.metadata_reader is not None
            else read_http_download_response_metadata(headers, max_bytes=self.max_bytes)
        )
        response_range = resolve_download_response_range(
            status_code=response.status_code,
            headers=headers,
            offset=self._requested_offset,
            content_length=metadata.declared_content_length,
        )
        final_url = str(response.url)
        etag = headers.get("ETag")
        strong_etag = (
            etag if etag is not None and re.fullmatch(r'"[!#-~\x80-\xff]*"', etag) else None
        )
        same_resource = final_url == self.final_url
        if same_resource and self._etag is not None and etag is not None and etag != self._etag:
            raise ValidationError("Artifact validator changed during the download.")
        if response.status_code == 206 and (
            not same_resource or strong_etag is None or strong_etag != self._etag
        ):
            self._force_full = True
            raise DownloadReplayRequired("The artifact continuation requires a full prefix replay.")
        total_length = response_range.total_length
        if self._persisted_unverified and total_length is not None and self.position > total_length:
            self._restart_persisted_prefix()
        if (
            self.total_length is not None
            and total_length is not None
            and total_length != self.total_length
        ):
            raise ValidationError("Artifact total length changed during the download.")
        if total_length is not None:
            if total_length < self.position:
                raise ValidationError("Artifact total length is smaller than the accepted prefix.")
            if self.max_bytes is not None and total_length > self.max_bytes:
                raise HTTPDownloadSizeLimitError("Artifact total length exceeds maximum size.")
        if (
            self.content_type is not None
            and metadata.content_type is not None
            and self.content_type != metadata.content_type
        ):
            raise ValidationError("Artifact content type changed during the download.")
        if total_length is not None:
            self.total_length = total_length
        if metadata.content_type is not None:
            self.content_type = metadata.content_type
        self.final_url = final_url
        self._etag = strong_etag
        self._response_length = metadata.declared_content_length
        if response.status_code == 206:
            if total_length is None:
                raise ValidationError("Artifact range has no total length.")
            self._response_length = total_length - response_range.offset
        self._response_received = 0
        self._replay_remaining = self.position if response.status_code == 200 else 0
        self._replay_digest = hashlib.sha256()
        self._force_full = self._replay_remaining > 0

    def consume(self, chunk: bytes) -> bytes:
        next_position = self.position + max(0, len(chunk) - self._replay_remaining)
        if self.max_bytes is not None and next_position > self.max_bytes:
            raise HTTPDownloadSizeLimitError(
                f"Download size ({next_position} bytes) exceeds maximum size ({self.max_bytes} bytes)."
            )
        received = self._response_received + len(chunk)
        if self._response_length is not None and received > self._response_length:
            raise ValidationError("Artifact response exceeds declared Content-Length.")
        self._response_received = received
        if self._replay_remaining:
            prefix_count = min(len(chunk), self._replay_remaining)
            self._replay_digest.update(chunk[:prefix_count])
            self._replay_remaining -= prefix_count
            chunk = chunk[prefix_count:]
            if self._replay_remaining:
                return b""
            expected_digest = (
                self._prefix_sha256 if self._persisted_unverified else self._digest.hexdigest()
            )
            if self._replay_digest.hexdigest() != expected_digest:
                if self._persisted_unverified:
                    self._restart_persisted_prefix()
                raise ValidationError("Artifact prefix changed during the download.")
            self._digest = self._replay_digest.copy()
            self._persisted_unverified = False
            self._force_full = False
        if self.total_length is not None and next_position > self.total_length:
            raise ValidationError("Download size exceeds declared total length.")
        self._digest.update(chunk)
        self.position = next_position
        return chunk

    def finish(self) -> None:
        if self._replay_remaining and self._persisted_unverified:
            self._restart_persisted_prefix()
        if (
            self._replay_remaining
            or (
                self._response_length is not None
                and self._response_received != self._response_length
            )
            or (self.total_length is not None and self.position != self.total_length)
        ):
            raise httpx2.RemoteProtocolError("Artifact response ended before the declared size.")

    def _restart_persisted_prefix(self) -> None:
        self.position = 0
        self.resumed_bytes = 0
        self.total_length = None
        self.content_type = None
        self.final_url = ""
        self._etag = None
        self._digest = hashlib.sha256()
        self._prefix_sha256 = None
        self._persisted_unverified = False
        self._replay_remaining = 0
        self._force_full = True
        raise DownloadReplayRequired("The retained artifact prefix requires a fresh download.")
