"""SoAI - HTML PDF header and footer templates [backend/core/browser/html_pdf_templates.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from functools import cache
from html import escape

from core.meta.version import __version__

__all__ = (
    "PDF_FONT_STACK_SANS",
    "build_pdf_footer_template",
    "build_pdf_header_template",
)

PDF_FONT_STACK_SANS = (
    '"SoAIType", system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", sans-serif'
)

_FOOTER_TOKEN_PATTERN_SOURCE = r"\{(page|total|version|date)\}"


@cache
def _footer_token_pattern() -> re.Pattern[str]:
    return re.compile(_FOOTER_TOKEN_PATTERN_SOURCE)


def build_pdf_header_template(*, title: str, logo_data_uri: str) -> str:
    safe_title = escape(title.strip(), quote=True)
    safe_logo = escape(logo_data_uri.strip(), quote=True)
    return f"""
<style>
  .soai-pdf-header {{
    box-sizing: border-box;
    width: 100%;
    padding: 0 14mm 4px;
    color: #687382;
    font-family: {PDF_FONT_STACK_SANS};
    font-size: 9px;
  }}
  .soai-pdf-header-row {{
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    border-bottom: 0.5px solid #d8dee6;
    padding-bottom: 4px;
  }}
  .soai-pdf-header-logo {{
    display: block;
    width: auto;
    height: 16px;
  }}
  .soai-pdf-header-title {{
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}
</style>
<div class="soai-pdf-header">
  <div class="soai-pdf-header-row">
    <img class="soai-pdf-header-logo" src="{safe_logo}">
    <span class="soai-pdf-header-title">{safe_title}</span>
  </div>
</div>
"""


def _render_footer_label(label: str, *, export_date: str) -> str:
    replacements = {
        "page": '<span class="pageNumber"></span>',
        "total": '<span class="totalPages"></span>',
        "version": escape(__version__, quote=True),
        "date": escape(export_date.strip(), quote=True),
    }
    return _footer_token_pattern().sub(
        lambda match: replacements[match.group(1)],
        escape(label.strip(), quote=True),
    )


def build_pdf_footer_template(*, note_label: str, pages_label: str, export_date: str) -> str:
    note = _render_footer_label(note_label, export_date=export_date)
    pages = _render_footer_label(pages_label, export_date=export_date)
    return f"""
<style>
  .soai-pdf-footer {{
    box-sizing: border-box;
    width: 100%;
    padding: 4px 14mm 0;
    color: #687382;
    font-family: {PDF_FONT_STACK_SANS};
    font-size: 9px;
  }}
  .soai-pdf-footer-row {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    border-top: 0.5px solid #d8dee6;
    padding-top: 4px;
  }}
</style>
<div class="soai-pdf-footer">
  <div class="soai-pdf-footer-row">
    <span>{note}</span>
    <span>{pages}</span>
  </div>
</div>
"""
