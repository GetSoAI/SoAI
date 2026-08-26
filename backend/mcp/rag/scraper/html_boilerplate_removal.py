"""SoAI - HTML scraper boilerplate element removal [backend/mcp/rag/scraper/html_boilerplate_removal.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from bs4 import BeautifulSoup, Tag

__all__ = (
    "is_likely_boilerplate_semantic",
    "remove_irrelevant_html",
)


def is_likely_boilerplate_semantic(node: Tag) -> bool:
    text = node.get_text(" ", strip=True)
    text_len = len(text)
    if text_len < 50:
        return True
    link_text_len = sum(len(anchor.get_text(" ", strip=True)) for anchor in node.find_all("a"))
    if text_len > 0 and link_text_len / text_len > 0.6:
        return True
    if node.name == "header" and node.find(["h1", "h2"]):
        return False
    return True


def remove_irrelevant_html(root: Tag | BeautifulSoup) -> None:
    for node in root.find_all(["script", "style", "noscript", "template"]):
        node.decompose()
    for node in list(root.find_all(["nav", "footer", "header", "aside", "form"])):
        if is_likely_boilerplate_semantic(node):
            node.decompose()
    for node in root.find_all(lambda tag: tag.has_attr("hidden")):
        node.decompose()
    for node in root.find_all(lambda tag: tag.get("aria-hidden") == "true"):
        node.decompose()
    unwanted_substrings = (
        "cookie",
        "consent",
        "banner",
        "modal",
        "popup",
        "subscribe",
        "newsletter",
        "advert",
        "ads",
        "sponsor",
        "social",
        "share",
        "breadcrumb",
        "pagination",
        "related",
        "recommend",
        "comments",
        "comment",
        "sidebar",
        "masthead",
        "toolbar",
        "nav",
        "footer",
        "header",
        "menu",
    )
    for node in list(root.find_all(True)):
        try:
            attrs = node.attrs
        except AttributeError:
            attrs = None
        if not attrs:
            continue
        id_raw = node.get("id")
        id_value = str(id_raw) if id_raw else ""
        raw_class = node.get("class")
        class_list = (
            raw_class if isinstance(raw_class, list) else ([raw_class] if raw_class else [])
        )
        class_value = " ".join(str(class_item) for class_item in class_list)
        combined = f"{id_value} {class_value}".lower()
        if combined and any(key in combined for key in unwanted_substrings):
            if node.name in {"html", "body", "main", "article"}:
                continue
            node.decompose()
