"""SoAI - Browser request routing inputs [backend/mcp/tools/browser/request_routing.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from playwright.async_api import Error

from core.browser_adblock.protocols import EasyListAdblockServiceProtocol
from core.browser_adblock.request_filter import (
    RequestFilterDecision,
    evaluate_request_filter,
)

if TYPE_CHECKING:
    from playwright.async_api import Request

__all__ = (
    "BrowserRequestRoutingEvaluation",
    "BrowserRequestRoutingInputs",
    "evaluate_browser_request_routing",
    "evaluate_request_routing_for_playwright_request",
    "resolve_request_routing_inputs",
)


@dataclass(frozen=True, slots=True)
class BrowserRequestRoutingInputs:
    request_url: str
    resource_type: str
    frame_url: str
    is_main_frame_document: bool | None
    referer: str | None


@dataclass(frozen=True, slots=True)
class BrowserRequestRoutingEvaluation:
    routing_inputs: BrowserRequestRoutingInputs
    decision: RequestFilterDecision


def resolve_request_routing_inputs(request: Request) -> BrowserRequestRoutingInputs:
    try:
        request_url = request.url
    except AttributeError:
        request_url = ""
    try:
        resource_type_value = request.resource_type
    except AttributeError:
        resource_type_value = ""
    try:
        frame = request.frame
        frame_url_value = frame.url
        frame_parent_value = frame.parent_frame
        is_main_frame_document: bool | None = frame_parent_value is None
    except (AttributeError, Error):
        frame_url_value = ""
        is_main_frame_document = None
    try:
        referer_value = request.headers.get("referer")
    except AttributeError:
        referer_value = None
    return BrowserRequestRoutingInputs(
        request_url=str(request_url or ""),
        resource_type=str(resource_type_value or ""),
        frame_url=str(frame_url_value or ""),
        is_main_frame_document=is_main_frame_document,
        referer=str(referer_value) if isinstance(referer_value, str) else None,
    )


def evaluate_browser_request_routing(
    *,
    routing_inputs: BrowserRequestRoutingInputs,
    block_images: bool,
    block_fonts: bool,
    block_media: bool,
    block_ads: bool,
    adblock_service: EasyListAdblockServiceProtocol | None,
) -> RequestFilterDecision:
    return evaluate_request_filter(
        request_url=routing_inputs.request_url,
        resource_type=routing_inputs.resource_type,
        is_main_frame_document=routing_inputs.is_main_frame_document,
        frame_url=routing_inputs.frame_url,
        referer=routing_inputs.referer,
        block_images=block_images,
        block_fonts=block_fonts,
        block_media=block_media,
        block_ads=block_ads,
        adblock_service=adblock_service,
    )


def evaluate_request_routing_for_playwright_request(
    request: Request,
    *,
    block_images: bool,
    block_fonts: bool,
    block_media: bool,
    block_ads: bool,
    adblock_service: EasyListAdblockServiceProtocol | None,
) -> BrowserRequestRoutingEvaluation:
    routing_inputs = resolve_request_routing_inputs(request)
    decision = evaluate_browser_request_routing(
        routing_inputs=routing_inputs,
        block_images=block_images,
        block_fonts=block_fonts,
        block_media=block_media,
        block_ads=block_ads,
        adblock_service=adblock_service,
    )
    return BrowserRequestRoutingEvaluation(routing_inputs=routing_inputs, decision=decision)
