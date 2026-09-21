"""SoAI - Immutable Tesseract model catalog [backend/core/media/tesseract_languages.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from string import ascii_lowercase

from core.errors.exceptions import StateError, ValidationError
from core.filesystem.open_files import open_text
from core.serialization.json_parsing import parse_json_dict
from core.serialization.sha256_hexdigest import require_canonical_sha256_hexdigest
from core.types.json import JSONDict, JSONValue

__all__ = (
    "DEFAULT_OCR_LANGUAGE",
    "TesseractLanguage",
    "TesseractDataFile",
    "TesseractCatalog",
    "get_tesseract_catalog",
    "require_ocr_language",
    "ocr_language_for_ui_locale",
)

DEFAULT_OCR_LANGUAGE = "eng"


@dataclass(frozen=True, slots=True)
class TesseractLanguage:
    code: str
    name: str
    native_name: str
    flag: str
    ui_locale: str | None
    sha256: str


@dataclass(frozen=True, slots=True)
class TesseractDataFile:
    code: str
    sha256: str


@dataclass(frozen=True, slots=True)
class TesseractCatalog:
    source_root: str
    license_sha256: str
    languages: tuple[TesseractLanguage, ...]
    auxiliaries: tuple[TesseractDataFile, ...]

    def data_files(self) -> tuple[TesseractDataFile, ...]:
        return (
            tuple(TesseractDataFile(entry.code, entry.sha256) for entry in self.languages)
            + self.auxiliaries
        )


def _require_text(entry: JSONDict, field: str) -> str:
    value = entry.get(field)
    if not isinstance(value, str):
        raise StateError(f"Invalid Tesseract catalog field: {field}.")
    if not value or value != value.strip():
        raise StateError(f"Empty or untrimmed Tesseract catalog field: {field}.")
    return value


@cache
def get_tesseract_catalog() -> TesseractCatalog:
    with open_text(os.path.join(os.path.dirname(__file__), "tesseract_languages.json")) as handle:
        catalog = parse_json_dict(handle.read(), field="Tesseract language catalog")
    languages_value = catalog.get("languages")
    auxiliaries_value = catalog.get("auxiliaries")
    if not isinstance(languages_value, list) or not isinstance(auxiliaries_value, list):
        raise StateError("Invalid Tesseract catalog model lists.")
    languages: list[TesseractLanguage] = []
    auxiliaries: list[TesseractDataFile] = []
    for entry in languages_value:
        if not isinstance(entry, dict):
            raise StateError("Invalid Tesseract catalog language.")
        ui_locale = entry.get("ui_locale")
        if ui_locale is not None and not isinstance(ui_locale, str):
            raise StateError("Invalid Tesseract catalog UI locale.")
        languages.append(
            TesseractLanguage(
                code=_require_text(entry, "code"),
                name=_require_text(entry, "name"),
                native_name=_require_text(entry, "native_name"),
                flag=_require_text(entry, "flag"),
                ui_locale=ui_locale,
                sha256=_require_text(entry, "sha256"),
            )
        )
    for entry in auxiliaries_value:
        if not isinstance(entry, dict):
            raise StateError("Invalid Tesseract catalog auxiliary.")
        auxiliaries.append(
            TesseractDataFile(_require_text(entry, "code"), _require_text(entry, "sha256"))
        )
    codes = [entry.code for entry in languages] + [entry.code for entry in auxiliaries]
    if len(set(codes)) != len(codes) or not any(
        entry.code == DEFAULT_OCR_LANGUAGE for entry in languages
    ):
        raise StateError("Invalid Tesseract catalog model identities.")
    result = TesseractCatalog(
        source_root=_require_text(catalog, "source_root"),
        license_sha256=require_canonical_sha256_hexdigest(
            _require_text(catalog, "license_sha256"), label="Tesseract data license digest"
        ),
        languages=tuple(languages),
        auxiliaries=tuple(auxiliaries),
    )
    for entry in result.data_files():
        if not entry.code.isascii() or not all(
            character in ascii_lowercase or character == "_" for character in entry.code
        ):
            raise StateError("Unsafe Tesseract catalog model identity.")
        require_canonical_sha256_hexdigest(entry.sha256, label="Tesseract model digest")
    locales = [entry.ui_locale for entry in languages if entry.ui_locale is not None]
    if len(set(locales)) != len(locales):
        raise StateError("Duplicate Tesseract catalog UI locale.")
    return result


def require_ocr_language(value: JSONValue) -> str:
    if not isinstance(value, str) or not any(
        entry.code == value for entry in get_tesseract_catalog().languages
    ):
        raise ValidationError("OCR language must be a supported single Tesseract model.")
    return value


def ocr_language_for_ui_locale(ui_locale: str) -> str:
    for entry in get_tesseract_catalog().languages:
        if entry.ui_locale == ui_locale:
            return entry.code
    raise ValidationError("Unsupported OCR initialization UI locale.")
