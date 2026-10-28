"""SoAI - Bounded discovery of explicitly referenced collection support files [backend/core/skills/collection_resources.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import posixpath
import re
from collections.abc import Callable

from core.archives.zip_plan import ValidatedZipMember
from core.skills.errors import build_skill_error
from core.skills.limits import MAX_PACKAGE_BYTES
from core.skills.packages import require_skill_file_capacity
from core.skills.records import SkillMember

__all__ = ("read_collection_supporting_members",)

_SOURCE_REFERENCE = (
    r"(?:\$\{CLAUDE_PLUGIN_ROOT\}|\$CLAUDE_PLUGIN_ROOT)/[A-Za-z0-9_./-]+|(?:\.\./)+[A-Za-z0-9_./-]+"
)
_CODE_IMPORT = r"(?:from\s+|import\s+|require\(\s*['\"]|from\s*['\"])([\w./-]+)"
_AGENT_REFERENCE = r"`([A-Za-z0-9][A-Za-z0-9_-]{0,127})`"


def read_collection_supporting_members(
    source_root: str,
    members: tuple[SkillMember, ...],
    indexed: dict[str, ValidatedZipMember],
    read_member: Callable[[str], SkillMember],
    *,
    plugin_root: str,
) -> tuple[SkillMember, ...]:
    owned = {f"{source_root}/{member.path}" if source_root else member.path for member in members}
    pending = [
        (f"{source_root}/{member.path}" if source_root else member.path, member)
        for member in members
        if not member.is_directory
    ]
    retained: dict[str, SkillMember] = {}
    expanded = sum(len(member.content) for member in members)
    files = sum(not member.is_directory for member in members)
    while pending:
        source_path, member = pending.pop()
        if b"\x00" in member.content:
            continue
        try:
            text = member.content.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        references: set[str] = set()
        if source_path == (f"{source_root}/SKILL.md" if source_root else "SKILL.md"):
            for match in re.finditer(_AGENT_REFERENCE, text):
                references.add(posixpath.join(plugin_root, "agents", f"{match.group(1)}.md"))
        direct_references = (
            re.finditer(_SOURCE_REFERENCE, text)
            if source_path in owned or source_path.endswith((".py", ".js", ".mjs", ".cjs", ".ts"))
            else ()
        )
        for match in direct_references:
            reference = match.group().rstrip(".,;")
            if reference.startswith("$"):
                reference = posixpath.join(plugin_root, reference.split("/", 1)[1])
            else:
                reference = posixpath.join(posixpath.dirname(source_path), reference)
            references.add(posixpath.normpath(reference))
        if source_path.endswith((".py", ".js", ".mjs", ".cjs", ".ts")):
            for match in re.finditer(_CODE_IMPORT, text):
                module = match.group(1)
                if module.startswith("."):
                    base = posixpath.normpath(
                        posixpath.join(posixpath.dirname(source_path), module)
                    )
                    references.update(
                        (
                            base,
                            f"{base}.js",
                            f"{base}.py",
                            f"{base}/__init__.py",
                            f"{base}/index.js",
                        )
                    )
                elif source_path.endswith(".py"):
                    base = posixpath.join(posixpath.dirname(source_path), module.replace(".", "/"))
                    references.update((f"{base}.py", f"{base}/__init__.py"))
        for reference in sorted(references):
            if reference in {"", ".", ".."} or reference.startswith(("../", "/")):
                continue
            candidates = (
                [reference] if reference in indexed and not indexed[reference].is_directory else []
            )
            for path in candidates:
                if path in owned or path in retained or path.rsplit("/", 1)[-1] == "SKILL.md":
                    continue
                entry = indexed[path]
                if expanded + entry.file_size > MAX_PACKAGE_BYTES:
                    raise build_skill_error(
                        "skill_invalid_package",
                        reason="resource_limit",
                        field="expanded_bytes",
                        measured=expanded + entry.file_size,
                        limit=MAX_PACKAGE_BYTES,
                    )
                require_skill_file_capacity(files + 1)
                support = read_member(path)
                retained[path] = support
                expanded += len(support.content)
                files += 1
                pending.append((path, support))
    return tuple(retained[path] for path in sorted(retained))
