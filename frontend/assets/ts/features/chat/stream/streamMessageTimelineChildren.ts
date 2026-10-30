/* SoAI - Chat feature stream message timeline children [frontend/assets/ts/features/chat/stream/streamMessageTimelineChildren.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { resolveHTMLElement, syncAttributes, syncClass } from '@core/dom/patching.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE } from '@features/chat/message/assistantResponseMarkup.ts';
import { patchInlineActivityHeaderChildrenInPlace } from '@features/chat/message/messageview/inlineActivityHeaderChildrenPatching.ts';
import { COLLAPSED_LOADING_CONTENT_SELECTOR, COLLAPSED_LOADING_SUMMARY_SELECTOR } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { resolveActiveImageWidgetsSignature } from '@features/chat/toolactivity/generatedImagePresentation.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { normalizeMultilineInput } from '@core/richtextrenderer/mappers.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME } from '@features/chat/message/assistantMessageMarkupParts.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { patchAssistantBodyChildrenInPlace, patchStreamingKeyedChildren } from '@features/chat/message/assistantBodyKeyedReconciler.ts';
import { patchStreamingTimelineSegmentInPlace, type StreamingTextSettlementProof } from '@features/chat/message/assistantTimelineSegmentPatching.ts';
import { buildTimelineRenderItems, type TimelineRenderItem } from '@features/chat/message/messageTimelineRenderItems.ts';
import type { StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import type { StreamMessageManager } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { STREAM_TEXT_SLOT_MARKUP } from '@features/chat/stream/streamMessageStreamingStructure.ts';

const LIVE_CONTENT_PRESERVED_ATTRIBUTE_NAMES = new Set<string>([ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME]);

const patchCollapsedLoadingSummary = (currentSummary: HTMLElement, nextSummary: HTMLElement): boolean => {
    const currentHeader = resolveHTMLElement(':scope > .inline-activity-header', currentSummary);
    const nextHeader = resolveHTMLElement(':scope > .inline-activity-header', nextSummary);
    if (!(currentHeader instanceof HTMLElement) || !(nextHeader instanceof HTMLElement)) {
        return false;
    }
    let changed = false;
    if (syncClass(currentSummary, nextSummary)) {
        changed = true;
    }
    if (syncAttributes({ target: currentSummary, source: nextSummary })) {
        changed = true;
    }
    if (patchInlineActivityHeaderChildrenInPlace(currentHeader, nextHeader)) {
        changed = true;
    }
    return changed;
};

export const patchCollapsedLoadingChrome = (target: HTMLElement, contentHtml: TrustedHtml): { patched: boolean; changed: boolean; summary: HTMLElement | null; widgetsChanged?: boolean } => {
    const currentSummary = dom.resolve(COLLAPSED_LOADING_SUMMARY_SELECTOR, target);
    const currentContent = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, target);
    if (!(currentSummary instanceof HTMLElement) || !(currentContent instanceof HTMLElement)) {
        return { patched: false, changed: false, summary: null };
    }
    const scratch = target.ownerDocument.createElement('div');
    replaceChildrenFromTrustedHtml({ element: scratch, html: contentHtml, context: scratch });
    const nextSummary = dom.resolve(COLLAPSED_LOADING_SUMMARY_SELECTOR, scratch);
    const nextContent = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, scratch);
    if (!(nextSummary instanceof HTMLElement) || !(nextContent instanceof HTMLElement)) {
        return { patched: false, changed: false, summary: null };
    }
    let changed = patchCollapsedLoadingSummary(currentSummary, nextSummary);
    if (syncAttributes({ target: currentContent, source: nextContent, preservedAttributeNames: LIVE_CONTENT_PRESERVED_ATTRIBUTE_NAMES })) {
        changed = true;
    }
    if (dom.resolve(`[${ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE}]`, target) === null && dom.resolve(`[${ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE}]`, scratch) === null) return { patched: true, changed, summary: currentSummary };
    const currentBody = currentContent.parentElement;
    const nextBody = nextContent.parentElement;
    if (!(currentBody instanceof HTMLElement) || !(nextBody instanceof HTMLElement)) return { patched: false, changed: false, summary: null };
    const widgetsChanged = patchAssistantBodyChildrenInPlace({
        container: currentBody,
        nextContainer: nextBody,
        patchExistingChild: (argumentsValue) => (argumentsValue.existing.hasAttribute(ASSISTANT_ACTIVITY_WIDGETS_ATTRIBUTE) ? patchStreamingTimelineSegmentInPlace(argumentsValue) : { patched: true, detailsChanged: false, retainedSignature: argumentsValue.existing.getAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME) ?? '' })
    });
    if (widgetsChanged === null) return { patched: false, changed: false, summary: null };
    return { patched: true, changed: changed || widgetsChanged, summary: currentSummary, widgetsChanged };
};

export interface ActiveStreamingTextRun {
    key: string;
    text: string;
}

const buildStreamingFlowLayout = (segments: MessageSegment[], messageManager: StreamMessageManager, cache: { markupByKey: Map<string, string> | null; signatureByKey: Map<string, string> | null }, includeWidgets: boolean): { activeTextRun: ActiveStreamingTextRun | null; items: TimelineRenderItem[] } => {
    const result = buildTimelineRenderItems({
        segments,
        nowMs: serverEpochMs(),
        renderSegment: (renderSegments, options) => messageManager.renderSegments(renderSegments, options),
        cache,
        activeTextSlot: { markup: STREAM_TEXT_SLOT_MARKUP },
        sortableTextTables: true
    });
    const signature = resolveActiveImageWidgetsSignature(segments);
    if (includeWidgets && signature !== '[]') {
        const key = 'assistant_activity_widgets:1';
        const cachedMarkup = cache.signatureByKey?.get(key) === signature ? cache.markupByKey?.get(key) : null;
        const markup = cachedMarkup ?? messageManager.renderAssistantActivityWidgets(segments, 'active');
        if (markup) result.items.push({ key, signature, markup, textSource: null });
    }
    return { activeTextRun: result.activeTextRun, items: result.items };
};

const resolveNonReplaceableActiveTextKeys = (activeTextRun: ActiveStreamingTextRun | null, cached: StreamingElementCache, streamSegments: HTMLElement): ReadonlySet<string> | null => {
    const streamText = cached.streamText;
    if (activeTextRun === null || !(streamText instanceof HTMLElement) || streamText.parentElement !== streamSegments || streamText.getAttribute('data-stream-text') !== 'true' || streamText.getAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME) !== activeTextRun.key) {
        return null;
    }
    return new Set<string>([activeTextRun.key]);
};

const resolveStreamingTextSettlementProof = (inputArguments: { cached: StreamingElementCache; item: TimelineRenderItem | undefined; existing: HTMLElement; messageManager: StreamMessageManager }): StreamingTextSettlementProof | null => {
    const cached = inputArguments.cached;
    const projection = cached.richTextProjection;
    if (inputArguments.item?.textSource === null || inputArguments.item?.textSource === undefined || projection === null || cached.activeStreamTextRunKey !== inputArguments.item.key || cached.streamText !== inputArguments.existing) {
        return null;
    }
    const settled = cached.streamTextSettled;
    const tail = cached.streamTextTail;
    if (!(settled instanceof HTMLElement) || !(tail instanceof HTMLElement) || settled.parentElement !== inputArguments.existing || tail.parentElement !== inputArguments.existing || settled === tail) {
        return null;
    }
    if (normalizeMultilineInput(inputArguments.item.textSource) !== projection.source || cached.richTextRenderEpoch !== inputArguments.messageManager.getWorkerRenderEpoch()) {
        return null;
    }
    const immutableNodes = cached.renderedRichBlocks.flatMap((record) => record.nodes);
    return {
        immutableNodes,
        settled,
        tail
    };
};

export const patchTimelineChildren = (message: ChatMessage, cached: StreamingElementCache, messageManager: StreamMessageManager, streamSegments: HTMLElement, segmentsOverride?: MessageSegment[] | null, includeWidgets = true): { supported: boolean; activeTextRun: ActiveStreamingTextRun | null; updated: boolean; changedElements: HTMLElement[] } => {
    const segments = segmentsOverride ?? messageManager.resolveMessageContentSegments(message);
    const layout = buildStreamingFlowLayout(segments, messageManager, { markupByKey: cached.segmentMarkupByKey, signatureByKey: cached.segmentSignatureByKey }, includeWidgets);
    const settlementItem = cached.activeStreamTextRunKey === null ? undefined : layout.items.find((item) => item.key === cached.activeStreamTextRunKey);
    const nonReplaceableKeys = resolveNonReplaceableActiveTextKeys(layout.activeTextRun, cached, streamSegments);
    const patchResult = patchStreamingKeyedChildren({
        container: streamSegments,
        items: layout.items,
        cachedMarkupByKey: cached.segmentMarkupByKey,
        cachedSignatureByKey: cached.segmentSignatureByKey,
        policy: {
            nonReplaceableKeys,
            disableInsertAnimation: false,
            applyStreamingReveal: true,
            applyStreamingRevealToTextBlocks: false
        },
        patchExistingChild: (patchArguments) => {
            const key = patchArguments.existing.getAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME) ?? '';
            return patchStreamingTimelineSegmentInPlace({
                ...patchArguments,
                streamingTextSettlementProof: resolveStreamingTextSettlementProof({ cached, item: settlementItem?.key === key ? settlementItem : undefined, existing: patchArguments.existing, messageManager })
            });
        },
        setCachedMarkupByKey: (map) => {
            cached.segmentMarkupByKey = map;
        },
        setCachedSignatureByKey: (map) => {
            cached.segmentSignatureByKey = map;
        }
    });
    return { supported: patchResult.supported, activeTextRun: layout.activeTextRun, updated: patchResult.updated, changedElements: patchResult.changedElements };
};
