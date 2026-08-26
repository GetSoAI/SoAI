"""SoAI - EasyList network rule parsing [backend/core/browser_adblock/rules.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = (
    "EasyListRule",
    "parse_easylist_rule",
    "parse_easylist_rules",
)

SUPPORTED_REQUEST_TYPES = frozenset(
    {
        "document",
        "font",
        "image",
        "media",
        "script",
        "stylesheet",
        "subdocument",
        "xmlhttprequest",
    },
)
COSMETIC_MARKERS = ("##", "#@#", "#?#", "#$#", "#@$#", "#%#", "#@%#")
UNSUPPORTED_OPTION_PREFIXES = (
    "badfilter",
    "csp=",
    "header=",
    "permissions=",
    "redirect=",
    "redirect-rule=",
    "removeparam=",
    "replace=",
    "rewrite=",
    "urltransform=",
)
SEPARATOR_PATTERN = r"(?:[^0-9A-Za-z_.%-]|$)"


@dataclass(frozen=True, slots=True)
class EasyListRule:
    raw_rule: str
    pattern: str
    regex_pattern: str
    is_exception: bool
    host_suffix: str | None
    included_domains: frozenset[str]
    excluded_domains: frozenset[str]
    included_request_types: frozenset[str]
    excluded_request_types: frozenset[str]
    third_party: bool | None
    important: bool


def parse_easylist_rules(rule_text: str) -> tuple[EasyListRule, ...]:
    parsed_rules: list[EasyListRule] = []
    disabled_rules: set[str] = set()
    for raw_line in rule_text.splitlines():
        disabled_rule = _parse_badfilter_target(raw_line)
        if disabled_rule is not None:
            disabled_rules.add(disabled_rule)
            continue
        parsed_rule = parse_easylist_rule(raw_line)
        if parsed_rule is not None:
            parsed_rules.append(parsed_rule)
    if not disabled_rules:
        return tuple(parsed_rules)
    return tuple(rule for rule in parsed_rules if rule.raw_rule not in disabled_rules)


def _parse_badfilter_target(raw_line: str) -> str | None:
    line = raw_line.strip()
    if not line or line.startswith("!") or line.startswith("["):
        return None
    if "$" not in line:
        return None
    pattern_text, options_text = _split_pattern_and_options(line)
    options = {option.strip().lower() for option in options_text.split(",") if option.strip()}
    if "badfilter" not in options:
        return None
    remaining_options = [
        option for option in options_text.split(",") if option.strip().lower() != "badfilter"
    ]
    if remaining_options:
        return f"{pattern_text}${','.join(remaining_options)}"
    return pattern_text


def parse_easylist_rule(raw_line: str) -> EasyListRule | None:
    line = raw_line.strip()
    if not line or line.startswith("!") or line.startswith("["):
        return None
    if "$$" in line or any(marker in line for marker in COSMETIC_MARKERS):
        return None
    is_exception = line.startswith("@@")
    normalized = line[2:] if is_exception else line
    if not normalized:
        return None
    pattern_text, options_text = _split_pattern_and_options(normalized)
    if not pattern_text:
        return None
    if pattern_text.startswith("||") and not re.match(r"^\|\|[0-9A-Za-z.*-]+", pattern_text):
        return None
    option_state = _parse_options(options_text)
    if option_state is None:
        return None
    regex_pattern, host_suffix = _compile_pattern(pattern_text)
    return EasyListRule(
        raw_rule=line,
        pattern=pattern_text,
        regex_pattern=regex_pattern,
        is_exception=is_exception,
        host_suffix=host_suffix,
        included_domains=option_state.included_domains,
        excluded_domains=option_state.excluded_domains,
        included_request_types=option_state.included_request_types,
        excluded_request_types=option_state.excluded_request_types,
        third_party=option_state.third_party,
        important=option_state.important,
    )


@dataclass(frozen=True, slots=True)
class _OptionState:
    included_domains: frozenset[str]
    excluded_domains: frozenset[str]
    included_request_types: frozenset[str]
    excluded_request_types: frozenset[str]
    third_party: bool | None
    important: bool


def _split_pattern_and_options(line: str) -> tuple[str, str]:
    if "$" not in line:
        return (line, "")
    pattern, options = line.split("$", 1)
    return (pattern.strip(), options.strip())


def _parse_options(options_text: str) -> _OptionState | None:
    included_domains: set[str] = set()
    excluded_domains: set[str] = set()
    included_request_types: set[str] = set()
    excluded_request_types: set[str] = set()
    third_party: bool | None = None
    important = False
    if not options_text:
        return _OptionState(
            included_domains=frozenset(),
            excluded_domains=frozenset(),
            included_request_types=frozenset(),
            excluded_request_types=frozenset(),
            third_party=None,
            important=False,
        )
    for raw_option in options_text.split(","):
        option = raw_option.strip().lower()
        if not option:
            continue
        if option == "important":
            important = True
            continue
        if option == "third-party":
            third_party = True
            continue
        if option == "~third-party":
            third_party = False
            continue
        if option.startswith("domain="):
            _parse_domain_option(
                option.removeprefix("domain="),
                included_domains=included_domains,
                excluded_domains=excluded_domains,
            )
            continue
        if option in SUPPORTED_REQUEST_TYPES:
            included_request_types.add(option)
            continue
        if option.startswith("~") and option[1:] in SUPPORTED_REQUEST_TYPES:
            excluded_request_types.add(option[1:])
            continue
        if option.startswith(UNSUPPORTED_OPTION_PREFIXES) or option in {"badfilter"}:
            return None
        return None
    return _OptionState(
        included_domains=frozenset(included_domains),
        excluded_domains=frozenset(excluded_domains),
        included_request_types=frozenset(included_request_types),
        excluded_request_types=frozenset(excluded_request_types),
        third_party=third_party,
        important=important,
    )


def _parse_domain_option(
    option_value: str,
    *,
    included_domains: set[str],
    excluded_domains: set[str],
) -> None:
    for raw_entry in option_value.split("|"):
        entry = raw_entry.strip().lower()
        if not entry:
            continue
        if entry.startswith("~"):
            excluded_domains.add(entry[1:])
            continue
        included_domains.add(entry)


def _compile_pattern(pattern: str) -> tuple[str, str | None]:
    if pattern.startswith("||"):
        host_suffix = _resolve_host_suffix(pattern)
        return (_translate_pattern(pattern), host_suffix)
    return (_translate_pattern(pattern), None)


def _resolve_host_suffix(pattern: str) -> str | None:
    host_match = re.match(r"^\|\|([0-9A-Za-z.-]+)", pattern)
    if host_match is None:
        return None
    host_suffix = host_match.group(1).lower()
    if not host_suffix or "*" in host_suffix:
        return None
    return host_suffix


def _translate_pattern(pattern: str) -> str:
    if pattern.startswith("||"):
        return _translate_host_anchored_pattern(pattern)
    translated = _translate_general_body(pattern)
    if pattern.startswith("|") and pattern.endswith("|") and len(pattern) > 1:
        return f"^{_translate_general_body(pattern[1:-1])}$"
    if pattern.startswith("|"):
        return f"^{_translate_general_body(pattern[1:])}"
    if pattern.endswith("|"):
        return f"{_translate_general_body(pattern[:-1])}$"
    return translated


def _translate_host_anchored_pattern(pattern: str) -> str:
    body = pattern[2:]
    host_text: list[str] = []
    tail_start = len(body)
    for index, character in enumerate(body):
        if character in {"/", "?", "#", "^", "|"}:
            tail_start = index
            break
        host_text.append(character)
    host_value = "".join(host_text)
    escaped_host = re.escape(host_value).replace(r"\*", ".*")
    tail_value = body[tail_start:]
    tail_regex = _translate_general_body(tail_value)
    return f"^[a-z][a-z0-9+\\-.]*://(?:[^/?#]*\\.)?{escaped_host}{tail_regex}"


def _translate_general_body(body: str) -> str:
    chunks: list[str] = []
    for character in body:
        if character == "*":
            chunks.append(".*")
            continue
        if character == "^":
            chunks.append(SEPARATOR_PATTERN)
            continue
        if character == "|":
            chunks.append(r"\|")
            continue
        chunks.append(re.escape(character))
    return "".join(chunks)
