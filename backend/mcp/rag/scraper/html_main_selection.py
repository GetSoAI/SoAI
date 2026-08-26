"""SoAI - Primary HTML content selection for scraping [backend/mcp/rag/scraper/html_main_selection.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

from core.errors.exception_logging import log_handled_exception
from core.errors.recoverable_exceptions import RECOVERABLE_EXCEPTIONS
from core.logging.trace import get_logger

__all__ = (
    "score_html_candidate",
    "select_main_html_node",
)

LOGGER_NAME = "SoAI.mcp.rag.html_main_selection"
OPERATION = "mcp.rag.scraper.html_main_selection.select_main_html_node"


def score_html_candidate(node: Tag) -> float:
    text = node.get_text(" ", strip=True) if node else ""
    text_len = len(text)
    if text_len < 200:
        return 0.0
    html_len = len(str(node))
    density = text_len / html_len if html_len > 0 else 0.0
    p_count = len(node.find_all("p"))
    li_count = len(node.find_all("li"))
    code_count = len(node.find_all(["pre", "code"]))
    heading_count = len(node.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]))
    link_text_len = sum(len(anchor.get_text(" ", strip=True)) for anchor in node.find_all("a"))
    bonus = 0.0
    if node.name in {"article", "main"}:
        bonus += 300.0
    id_raw = node.get("id")
    id_value = (str(id_raw) if id_raw else "").lower()
    raw_class = node.get("class")
    class_list = raw_class if isinstance(raw_class, list) else ([raw_class] if raw_class else [])
    class_value = " ".join(str(class_item) for class_item in class_list).lower()
    combined = f"{id_value} {class_value}"
    for token in ("content", "article", "post", "entry", "main", "body", "text", "markdown"):
        if token in combined:
            bonus += 120.0
    density_bonus = density * 200.0
    heading_bonus = min(heading_count, 6) * 30.0
    score = (
        float(text_len)
        + p_count * 60.0
        + li_count * 25.0
        + code_count * 20.0
        + heading_bonus
        + density_bonus
        - link_text_len * 0.5
        + bonus
    )
    return max(score, 0.0)


def select_main_html_node(soup: BeautifulSoup) -> Tag | BeautifulSoup:
    logger = get_logger(LOGGER_NAME)
    candidates: list[Tag] = []
    for selector in ("article", "main", "[role=main]", "#main", "#content", "#primary", "body"):
        try:
            candidates.extend(soup.select(selector))
        except RECOVERABLE_EXCEPTIONS as exception:
            log_handled_exception(
                logger,
                exception,
                message="Failed to select candidate node from HTML (non-critical).",
                operation=OPERATION,
                details={"selector": selector},
                level="debug",
            )
            continue
    for tag_name in ("article", "main", "section", "div"):
        for node in soup.find_all(tag_name):
            id_raw = node.get("id")
            id_value = (str(id_raw) if id_raw else "").lower()
            raw_class = node.get("class")
            class_list = (
                raw_class if isinstance(raw_class, list) else ([raw_class] if raw_class else [])
            )
            class_value = " ".join(str(class_item) for class_item in class_list).lower()
            combined = f"{id_value} {class_value}"
            if any(
                token in combined
                for token in ("content", "article", "post", "entry", "main", "body", "text")
            ):
                candidates.append(node)
    best_node: Tag | None = None
    best_score = 0.0
    seen: set[int] = set()
    for node in candidates:
        node_identity = id(node)
        if node_identity in seen:
            continue
        seen.add(node_identity)
        score = score_html_candidate(node)
        if score > best_score:
            best_score = score
            best_node = node
    return best_node or (soup.find("body") or soup)
