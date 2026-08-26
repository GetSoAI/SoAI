"""SoAI - GDELT Article List parsing and matching [backend/mcp/tools/news_gal_payload.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

import gzip
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING

from core.errors.exceptions import ValidationError
from core.errors.external_service_exception import ExternalServiceError
from core.network.urls import require_absolute_http_url
from core.serialization.json_parsing import parse_json_dict
from core.validation.strings import coerce_trimmed_str_or_empty

if TYPE_CHECKING:
    from core.types.json import JSONDict
    from mcp.tools.news_query import NewsRequest

__all__ = ("GalArticle", "build_gal_provider_payload", "parse_gal_payload")

_MAX_UNCOMPRESSED_BYTES = 16_777_216
_CONTIGUOUS_SCRIPT_LANGUAGES: frozenset[str] = frozenset({"ja", "ko", "zh"})


@dataclass(frozen=True, slots=True)
class GalArticle:
    published: str
    url: str
    domain: str
    title: str
    image: str
    description: str
    language: str


def _read_gzip_text(body: bytes) -> str:
    try:
        with gzip.GzipFile(fileobj=BytesIO(body), mode="rb") as archive:
            raw_text = archive.read(_MAX_UNCOMPRESSED_BYTES + 1)
    except (EOFError, OSError) as exception:
        raise ExternalServiceError("GDELT Article List archive is invalid.") from exception
    if len(raw_text) > _MAX_UNCOMPRESSED_BYTES:
        raise ExternalServiceError("GDELT Article List archive exceeds its size limit.")
    try:
        return raw_text.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exception:
        raise ExternalServiceError("GDELT Article List must be valid UTF-8.") from exception


def _parse_article(entry: JSONDict) -> GalArticle | None:
    title = coerce_trimmed_str_or_empty(entry.get("title"))
    raw_url = coerce_trimmed_str_or_empty(entry.get("url"))
    domain = coerce_trimmed_str_or_empty(entry.get("domain"))
    published = coerce_trimmed_str_or_empty(entry.get("date"))
    language = coerce_trimmed_str_or_empty(entry.get("lang")).lower()
    if not title or not raw_url or not domain or not published or not language:
        return None
    try:
        url = require_absolute_http_url(raw_url)
    except ValidationError:
        return None
    return GalArticle(
        published=published,
        url=url,
        domain=domain,
        title=title,
        image=coerce_trimmed_str_or_empty(entry.get("image")),
        description=coerce_trimmed_str_or_empty(entry.get("desc")),
        language=language,
    )


def parse_gal_payload(body: bytes) -> tuple[GalArticle, ...]:
    text = _read_gzip_text(body)
    articles: list[GalArticle] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            entry = parse_json_dict(
                raw_line,
                field=f"GDELT Article List line {line_number}",
                reject_duplicate_keys=True,
            )
        except ValidationError as exception:
            raise ExternalServiceError("GDELT Article List contains invalid JSON.") from exception
        article = _parse_article(entry)
        if article is not None:
            articles.append(article)
    return tuple(articles)


def _normalized_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _word_tokens(value: str) -> tuple[str, ...]:
    normalized = _normalized_text(value)
    tokens: list[str] = []
    current: list[str] = []
    for character in normalized:
        if character.isalnum():
            current.append(character)
            continue
        if current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def _article_matches(article: GalArticle, request: NewsRequest) -> bool:
    if article.language != request.language:
        return False
    if request.top_headlines or request.start_datetime is not None:
        return True
    searchable = f"{article.title} {article.description}"
    query_tokens = _word_tokens(request.query)
    if not query_tokens:
        return False
    if request.language in _CONTIGUOUS_SCRIPT_LANGUAGES:
        normalized_searchable = _normalized_text(searchable)
        return all(query_token in normalized_searchable for query_token in query_tokens)
    article_tokens = frozenset(_word_tokens(searchable))
    return all(query_token in article_tokens for query_token in query_tokens)


def build_gal_provider_payload(
    batches: tuple[tuple[GalArticle, ...], ...],
    request: NewsRequest,
) -> JSONDict:
    articles: list[JSONDict] = []
    seen_urls: set[str] = set()
    for batch in batches:
        for article in batch:
            if article.url in seen_urls or not _article_matches(article, request):
                continue
            seen_urls.add(article.url)
            articles.append(
                {
                    "title": article.title,
                    "url": article.url,
                    "domain": article.domain,
                    "seendate": article.published,
                    "socialimage": article.image,
                },
            )
            if len(articles) >= request.max_results:
                return {"articles": articles}
    return {"articles": articles}
