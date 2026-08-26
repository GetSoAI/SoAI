"""SoAI - EasyList matcher compilation and evaluation [backend/core/browser_adblock/matcher.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass

from core.browser_adblock.rules import EasyListRule

__all__ = (
    "CompiledEasyListRule",
    "EasyListMatchResult",
    "EasyListMatcher",
)


@dataclass(frozen=True, slots=True)
class CompiledEasyListRule:
    source: EasyListRule


@dataclass(frozen=True, slots=True)
class EasyListMatchResult:
    matched: bool
    rule_text: str | None


class EasyListMatcher:
    __slots__ = (
        "_allow_generic_rules",
        "_allow_host_rules",
        "_block_generic_rules",
        "_block_host_rules",
        "_regex_cache",
    )

    def __init__(self, rules: tuple[EasyListRule, ...]) -> None:
        allow_host_rules: dict[str, tuple[CompiledEasyListRule, ...]] = {}
        block_host_rules: dict[str, tuple[CompiledEasyListRule, ...]] = {}
        allow_generic_rules: list[CompiledEasyListRule] = []
        block_generic_rules: list[CompiledEasyListRule] = []
        compiled_rules = [CompiledEasyListRule(source=rule) for rule in rules]
        for compiled_rule in compiled_rules:
            target = allow_host_rules if compiled_rule.source.is_exception else block_host_rules
            if compiled_rule.source.host_suffix is not None:
                existing_rules = list(target.get(compiled_rule.source.host_suffix, ()))
                existing_rules.append(compiled_rule)
                target[compiled_rule.source.host_suffix] = tuple(existing_rules)
                continue
            if compiled_rule.source.is_exception:
                allow_generic_rules.append(compiled_rule)
                continue
            block_generic_rules.append(compiled_rule)
        self._allow_host_rules = allow_host_rules
        self._block_host_rules = block_host_rules
        self._allow_generic_rules = tuple(allow_generic_rules)
        self._block_generic_rules = tuple(block_generic_rules)
        self._regex_cache: OrderedDict[str, re.Pattern[str]] = OrderedDict()

    def match(
        self,
        request_url: str,
        *,
        request_host: str | None,
        request_type: str | None,
        document_host: str | None,
        is_third_party: bool | None,
    ) -> EasyListMatchResult:
        block_candidates = self._collect_candidates(
            self._block_host_rules,
            self._block_generic_rules,
            request_host,
        )
        matched_important_block = self._find_match(
            block_candidates,
            request_url=request_url,
            request_type=request_type,
            document_host=document_host,
            is_third_party=is_third_party,
            important_only=True,
        )
        if matched_important_block is not None:
            return EasyListMatchResult(
                matched=True,
                rule_text=matched_important_block.source.raw_rule,
            )
        matched_block = self._find_match(
            block_candidates,
            request_url=request_url,
            request_type=request_type,
            document_host=document_host,
            is_third_party=is_third_party,
            important_only=False,
        )
        if matched_block is None:
            return EasyListMatchResult(matched=False, rule_text=None)
        allow_candidates = self._collect_candidates(
            self._allow_host_rules,
            self._allow_generic_rules,
            request_host,
        )
        matched_allow = self._find_match(
            allow_candidates,
            request_url=request_url,
            request_type=request_type,
            document_host=document_host,
            is_third_party=is_third_party,
            important_only=False,
        )
        if matched_allow is not None:
            return EasyListMatchResult(matched=False, rule_text=matched_allow.source.raw_rule)
        return EasyListMatchResult(matched=True, rule_text=matched_block.source.raw_rule)

    def _collect_candidates(
        self,
        host_rules: dict[str, tuple[CompiledEasyListRule, ...]],
        generic_rules: tuple[CompiledEasyListRule, ...],
        request_host: str | None,
    ) -> tuple[CompiledEasyListRule, ...]:
        if request_host is None:
            return generic_rules
        candidates: list[CompiledEasyListRule] = list(generic_rules)
        host_parts = [part for part in request_host.split(".") if part]
        for index in range(len(host_parts)):
            suffix = ".".join(host_parts[index:])
            candidates.extend(host_rules.get(suffix, ()))
        return tuple(candidates)

    def _find_match(
        self,
        candidates: tuple[CompiledEasyListRule, ...],
        *,
        request_url: str,
        request_type: str | None,
        document_host: str | None,
        is_third_party: bool | None,
        important_only: bool,
    ) -> CompiledEasyListRule | None:
        for candidate in candidates:
            if important_only and not candidate.source.important:
                continue
            if not _domains_match(candidate.source, document_host):
                continue
            if not _request_type_matches(candidate.source, request_type):
                continue
            if not _third_party_matches(candidate.source, is_third_party):
                continue
            regex = self._get_regex(candidate.source.regex_pattern)
            if regex.search(request_url) is None:
                continue
            return candidate
        return None

    def _get_regex(self, pattern: str) -> re.Pattern[str]:
        cached = self._regex_cache.get(pattern)
        if cached is not None:
            self._regex_cache.move_to_end(pattern)
            return cached
        compiled = re.compile(pattern, re.IGNORECASE)
        self._regex_cache[pattern] = compiled
        if len(self._regex_cache) > 2048:
            self._regex_cache.popitem(last=False)
        return compiled


def _domains_match(rule: EasyListRule, document_host: str | None) -> bool:
    if not rule.included_domains and not rule.excluded_domains:
        return True
    if document_host is None:
        return False
    if rule.excluded_domains and any(
        _domain_matches(document_host, entry) for entry in rule.excluded_domains
    ):
        return False
    if not rule.included_domains:
        return True
    return any(_domain_matches(document_host, entry) for entry in rule.included_domains)


def _domain_matches(document_host: str, domain_rule: str) -> bool:
    return document_host == domain_rule or document_host.endswith(f".{domain_rule}")


def _request_type_matches(rule: EasyListRule, request_type: str | None) -> bool:
    if request_type is None:
        return not rule.included_request_types
    if request_type in rule.excluded_request_types:
        return False
    if not rule.included_request_types:
        return True
    return request_type in rule.included_request_types


def _third_party_matches(rule: EasyListRule, is_third_party: bool | None) -> bool:
    if rule.third_party is None:
        return True
    if is_third_party is None:
        return False
    return rule.third_party is is_third_party
