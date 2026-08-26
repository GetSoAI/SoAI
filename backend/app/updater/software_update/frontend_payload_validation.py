"""SoAI - Built frontend update payload validation [backend/app/updater/software_update/frontend_payload_validation.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from html.parser import HTMLParser
from typing import TYPE_CHECKING, override
from urllib.parse import urlsplit

from core.errors.exceptions import ValidationError
from core.filesystem.open_files import open_binary, open_text
from core.serialization.json_parsing import parse_json_dict
from core.types.json_value import require_json_dict

if TYPE_CHECKING:
    from core.types.json import JSONDict, JSONValue

__all__ = ("validate_staged_frontend",)

REQUIRED_FRONTEND_ENTRIES = (
    "entries/critical.ts",
    "entries/main.ts",
    "entries/detached.ts",
)


class LocalAssetReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []

    @override
    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        for attribute_name, attribute_value in attrs:
            if attribute_name in {"href", "src"} and attribute_value is not None:
                if attribute_value.startswith("./"):
                    self.references.append(attribute_value)


def _require_build_path(value: JSONValue, *, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValidationError(f"{field} must be a non-empty canonical path.")
    if value.startswith("/") or value.endswith("/") or "\\" in value or "\x00" in value:
        raise ValidationError(f"{field} must be a safe relative path.")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValidationError(f"{field} must be a safe relative path.")
    return value


def _require_string_array(value: JSONValue, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be an array.")
    paths: list[str] = []
    for item in value:
        paths.append(_require_build_path(item, field=field))
    return tuple(paths)


def _require_manifest_record_names(value: JSONValue, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValidationError(f"{field} must be an array.")
    record_names: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or item != item.strip()
            or "\\" in item
            or "\x00" in item
        ):
            raise ValidationError(f"{field} must contain canonical manifest record names.")
        record_names.append(item)
    return tuple(record_names)


def _require_regular_build_file(build_root: str, relative_path: str) -> None:
    candidate = os.path.abspath(os.path.join(build_root, *relative_path.split("/")))
    build_prefix = f"{os.path.abspath(build_root)}{os.sep}"
    if not candidate.startswith(build_prefix) or not os.path.isfile(candidate):
        raise ValidationError(f"Frontend build manifest references missing file: {relative_path}")
    if os.path.islink(candidate):
        raise ValidationError(f"Frontend build manifest references a symlink: {relative_path}")


def _validate_manifest_record(
    *,
    manifest: JSONDict,
    record_name: str,
    record: JSONDict,
    build_root: str,
) -> tuple[str, tuple[str, ...]]:
    output_file = _require_build_path(record.get("file"), field=f"{record_name}.file")
    _require_regular_build_file(build_root, output_file)
    css_files = _require_string_array(record.get("css"), field=f"{record_name}.css")
    asset_files = _require_string_array(record.get("assets"), field=f"{record_name}.assets")
    for relative_path in (*css_files, *asset_files):
        _require_regular_build_file(build_root, relative_path)
    for dependency_field in ("imports", "dynamicImports"):
        dependencies = _require_manifest_record_names(
            record.get(dependency_field),
            field=f"{record_name}.{dependency_field}",
        )
        for dependency in dependencies:
            if dependency not in manifest:
                raise ValidationError(
                    f"Frontend build manifest references missing entry: {dependency}",
                )
    return (output_file, css_files)


def _read_text(path: str) -> str:
    with open_text(path, encoding="utf-8", errors="strict") as file_handle:
        return file_handle.read()


def _read_json(path: str, *, field: str) -> JSONDict:
    try:
        with open_binary(path, mode="rb") as file_handle:
            return parse_json_dict(
                file_handle.read(),
                field=field,
                reject_duplicate_keys=True,
            )
    except OSError as exception:
        raise ValidationError(f"{field} is missing or unreadable.") from exception


def _require_html_reference(html: str, relative_path: str, *, html_name: str) -> None:
    expected = f"./assets/build/{relative_path}"
    if expected not in html:
        raise ValidationError(f"{html_name} does not reference frontend bundle: {relative_path}")


def _require_html_assets(
    html: str,
    *,
    html_name: str,
    asset_roots: tuple[str, ...],
) -> None:
    parser = LocalAssetReferenceParser()
    parser.feed(html)
    for reference in parser.references:
        parsed_reference = urlsplit(reference)
        relative_path = _require_build_path(
            parsed_reference.path.removeprefix("./"),
            field=f"{html_name} asset",
        )
        if any(
            os.path.isfile(os.path.join(asset_root, *relative_path.split("/")))
            and not os.path.islink(os.path.join(asset_root, *relative_path.split("/")))
            for asset_root in asset_roots
        ):
            continue
        raise ValidationError(f"{html_name} references missing asset: {relative_path}")


def _validate_build_input_manifest(
    *,
    build_root: str,
    expected_edition: str,
) -> None:
    input_manifest = _read_json(
        os.path.join(build_root, "build-input-manifest-v1.json"),
        field="frontend build input manifest",
    )
    if set(input_manifest) != {"schema_version", "edition", "module_ids"}:
        raise ValidationError("Frontend build input manifest fields are invalid.")
    if input_manifest.get("schema_version") != 1:
        raise ValidationError("Frontend build input manifest schema is invalid.")
    if input_manifest.get("edition") != expected_edition:
        raise ValidationError("Frontend build input manifest edition is invalid.")
    module_ids = input_manifest.get("module_ids")
    if (
        not isinstance(module_ids, list)
        or not module_ids
        or any(not isinstance(module_id, str) or not module_id for module_id in module_ids)
    ):
        raise ValidationError("Frontend build input manifest module inventory is invalid.")
    private_inputs = tuple(
        module_id
        for module_id in module_ids
        if isinstance(module_id, str)
        and (module_id.startswith("soai_os/") or module_id.startswith("virtual:soai_os/"))
    )
    if expected_edition == "soai-core" and private_inputs:
        raise ValidationError("Core frontend bundle contains SoAI OS modules.")
    if expected_edition == "soai-os" and not private_inputs:
        raise ValidationError("SoAI OS frontend bundle contains no private modules.")


def validate_staged_frontend(
    staged_root: str,
    *,
    frontend_relative_path: str,
    expected_edition: str,
    fallback_relative_paths: tuple[str, ...],
) -> None:
    if expected_edition not in {"soai-core", "soai-os"}:
        raise ValidationError("Frontend edition must be soai-core or soai-os.")
    relative_frontend_root = _require_build_path(
        frontend_relative_path,
        field="frontend root",
    )
    frontend_root = os.path.join(staged_root, *relative_frontend_root.split("/"))
    fallback_roots = tuple(
        os.path.join(
            staged_root,
            *_require_build_path(relative_path, field="frontend fallback root").split("/"),
        )
        for relative_path in fallback_relative_paths
    )
    asset_roots = (frontend_root, *fallback_roots)
    build_root = os.path.join(frontend_root, "assets", "build")
    manifest_path = os.path.join(build_root, "manifest.json")
    manifest = _read_json(manifest_path, field="frontend build manifest")
    _validate_build_input_manifest(
        build_root=build_root,
        expected_edition=expected_edition,
    )
    resolved_entries: dict[str, tuple[str, tuple[str, ...]]] = {}
    for record_name, raw_record in manifest.items():
        record = require_json_dict(raw_record, label=f"frontend manifest {record_name}")
        resolved_entries[record_name] = _validate_manifest_record(
            manifest=manifest,
            record_name=record_name,
            record=record,
            build_root=build_root,
        )
    for entry_name in REQUIRED_FRONTEND_ENTRIES:
        if entry_name not in resolved_entries:
            raise ValidationError(f"Frontend build manifest is missing entry: {entry_name}")
        entry_record = require_json_dict(manifest[entry_name], label=entry_name)
        if entry_record.get("isEntry") is not True or entry_record.get("src") != entry_name:
            raise ValidationError(f"Frontend build manifest entry is invalid: {entry_name}")
    main_file, main_css = resolved_entries["entries/main.ts"]
    critical_file, _ = resolved_entries["entries/critical.ts"]
    detached_file, _ = resolved_entries["entries/detached.ts"]
    if len({main_file, critical_file, detached_file}) != 3:
        raise ValidationError("Frontend entry bundles must be distinct files.")
    if not main_css:
        raise ValidationError("Frontend main entry must reference at least one CSS bundle.")
    index_html = _read_text(os.path.join(frontend_root, "index.html"))
    detached_html = _read_text(os.path.join(frontend_root, "detached.html"))
    for relative_path in (critical_file, main_file, *main_css):
        _require_html_reference(index_html, relative_path, html_name="frontend/index.html")
    for relative_path in (critical_file, detached_file, *main_css):
        _require_html_reference(detached_html, relative_path, html_name="frontend/detached.html")
    _require_html_assets(
        index_html,
        html_name=f"{frontend_relative_path}/index.html",
        asset_roots=asset_roots,
    )
    _require_html_assets(
        detached_html,
        html_name=f"{frontend_relative_path}/detached.html",
        asset_roots=asset_roots,
    )
