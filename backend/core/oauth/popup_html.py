"""SoAI - Shared OAuth popup completion HTML [backend/core/oauth/popup_html.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from core.serialization.json import serialize_json_compact_stable
from core.types.json import JSONDict

__all__ = ("build_popup_html",)

_SCRIPT_CONTEXT_JSON_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("<", "\\u003c"),
    (">", "\\u003e"),
    ("&", "\\u0026"),
    ("\u2028", "\\u2028"),
    ("\u2029", "\\u2029"),
)


def _escape_json_for_script_context(json_text: str) -> str:
    escaped = json_text
    for needle, replacement in _SCRIPT_CONTEXT_JSON_REPLACEMENTS:
        escaped = escaped.replace(needle, replacement)
    return escaped


def build_popup_html(payload: JSONDict) -> str:
    json_payload = _escape_json_for_script_context(serialize_json_compact_stable(payload))
    return f"""<!doctype html>
<html>
  <body>
    <script>
      (function() {{
        try {{
          if (window.opener) {{
            window.opener.postMessage({json_payload}, window.location.origin);
          }}
        }} finally {{
          window.close();
        }}
      }})();
    </script>
  </body>
</html>
"""
