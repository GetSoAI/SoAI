"""SoAI - Terminal key sequences [backend/core/terminal/key_sequences.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.errors.exceptions import ValidationError

__all__ = ("encode_key_sequence",)

_ESC: bytes = b"\x1b"
_CSI: bytes = b"\x1b["
_SS3: bytes = b"\x1bO"


def encode_key_sequence(key: str) -> bytes:
    normalized = str(key or "").strip()
    if not normalized:
        raise ValidationError("Key must be a non-empty string.")
    if normalized == "ArrowUp":
        return _CSI + b"A"
    if normalized == "ArrowDown":
        return _CSI + b"B"
    if normalized == "ArrowRight":
        return _CSI + b"C"
    if normalized == "ArrowLeft":
        return _CSI + b"D"
    if normalized == "Home":
        return _CSI + b"H"
    if normalized == "End":
        return _CSI + b"F"
    if normalized == "PageUp":
        return _CSI + b"5~"
    if normalized == "PageDown":
        return _CSI + b"6~"
    if normalized == "Insert":
        return _CSI + b"2~"
    if normalized == "Delete":
        return _CSI + b"3~"
    if normalized == "Escape":
        return _ESC
    if normalized == "Enter":
        return b"\n"
    if normalized == "Tab":
        return b"\t"
    if normalized == "Shift+Tab":
        return _CSI + b"Z"
    if normalized == "Backspace":
        return b"\x7f"
    if normalized == "F1":
        return _SS3 + b"P"
    if normalized == "F2":
        return _SS3 + b"Q"
    if normalized == "F3":
        return _SS3 + b"R"
    if normalized == "F4":
        return _SS3 + b"S"
    if normalized == "F5":
        return _CSI + b"15~"
    if normalized == "F6":
        return _CSI + b"17~"
    if normalized == "F7":
        return _CSI + b"18~"
    if normalized == "F8":
        return _CSI + b"19~"
    if normalized == "F9":
        return _CSI + b"20~"
    if normalized == "F10":
        return _CSI + b"21~"
    if normalized == "F11":
        return _CSI + b"23~"
    if normalized == "F12":
        return _CSI + b"24~"
    if normalized.startswith("Ctrl+"):
        suffix = normalized[5:].strip()
        if len(suffix) != 1:
            raise ValidationError(f"Unsupported key: {normalized}")
        ch = suffix.upper()
        if ch < "A" or ch > "Z":
            raise ValidationError(f"Unsupported key: {normalized}")
        return bytes([ord(ch) - ord("A") + 1])
    raise ValidationError(f"Unsupported key: {normalized}")
