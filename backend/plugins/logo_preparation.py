"""SoAI - Identity-bound optional archive artwork preparation [backend/plugins/logo_preparation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os

from core.concurrency.ttl_cache import TTLCache
from core.errors.exceptions import StateError
from core.files.content_hashing import hash_seekable_binary_stream_content
from core.files.file_identity import FileIdentity
from core.filesystem.open_files import open_regular_binary_no_symlink
from core.plugins.logo_contract import PluginLogoResult
from core.plugins.logo_images import sanitize_plugin_logo
from plugins.package_inspection import inspect_plugin_package_stream

__all__ = ("prepare_archive_logo",)


def prepare_archive_logo(
    plugin_name: str,
    archive_path: str,
    archive_hash: str,
    cache: TTLCache[tuple[str, FileIdentity], PluginLogoResult],
) -> PluginLogoResult:
    with open_regular_binary_no_symlink(
        archive_path,
        not_found_message="Plugin artwork source was not found.",
        symlink_message="Plugin artwork source is a symbolic link.",
        open_message="Plugin artwork source could not be opened.",
        inspect_message="Plugin artwork source could not be inspected.",
        regular_file_message="Plugin artwork source is not a regular file.",
    ) as source:
        identity = FileIdentity.from_stat(os.fstat(source.fileno()))
        content_hash = hash_seekable_binary_stream_content(source)
        if content_hash.sha256_hex != archive_hash:
            raise StateError("Plugin artwork source does not match the catalog revision.")
        cache_key = (archive_hash, identity)
        result = cache.get(cache_key)
        reconstructed = result is None
        if result is None:
            snapshot = inspect_plugin_package_stream(plugin_name, source)
            if snapshot.content.archive_hash != content_hash.sha256_hex:
                raise StateError("Plugin artwork source does not match the catalog revision.")
            result = sanitize_plugin_logo(snapshot.logo_source)
        if not identity.matches_descriptor_snapshot(
            FileIdentity.from_stat(os.fstat(source.fileno())),
        ):
            raise StateError("Plugin artwork source changed during preparation.")
        if identity != FileIdentity.from_stat(os.stat(archive_path, follow_symlinks=False)):
            raise StateError("Plugin artwork source was replaced during preparation.")
        if reconstructed:
            cache.put(cache_key, result)
        return result
