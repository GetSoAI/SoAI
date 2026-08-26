/* SoAI - Chat feature stream message timeline children [frontend/assets/ts/features/chat/stream/streamMessageTimelineChildren.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serverEpochMs } from '@core/time/clock.ts';
import { normalizeMultilineInput } from '@core/richtextrenderer/mappers.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME } from '@features/chat/message/assistantMessageMarkupParts.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { patchStreamingKeyedChildren } from '@features/chat/message/assistantBodyKeyedReconciler.ts';
import { patchStreamingTimelineSegmentInPlace, type StreamingTextSettlementProof } from '@features/chat/message/assistantTimelineSegmentPatching.ts';
import { buildTimelineRenderItems, type TimelineRenderItem } from '@features/chat/message/messageTimelineRenderItems.ts';
import type { StreamingElementCache } from '@features/chat/stream/streamDomCache.ts';
import type { StreamMessageManager } from '@features/chat/stream/streamMessageRenderingContracts.ts';
import { STREAM_TEXT_SLOT_MARKUP } from '@features/chat/stream/streamMessageStreamingStructure.ts';

export interface ActiveStreamingTextRun {
    key: string;
    text: string;
}

const buildStreamingFlowLayout = (segments: MessageSegment[], messageManager: StreamMessageManager, cache: { markupByKey: Map<string, string> | null; signatureByKey: Map<string, string> | null }): { activeTextRun: ActiveStreamingTextRun | null; items: TimelineRenderItem[] } => {
    const result = buildTimelineRenderItems({
        segments,
        nowMs: serverEpochMs(),
        renderSegment: (renderSegments, options) => messageManager.renderSegments(renderSegments, options),
        cache,
        activeTextSlot: { markup: STREAM_TEXT_SLOT_MARKUP },
        sortableTextTables: true
    });
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

export const patchTimelineChildren = (message: ChatMessage, cached: StreamingElementCache, messageManager: StreamMessageManager, streamSegments: HTMLElement, segmentsOverride?: MessageSegment[] | null): { supported: boolean; activeTextRun: ActiveStreamingTextRun | null; updated: boolean; changedElements: HTMLElement[] } => {
    const segments = segmentsOverride ?? messageManager.resolveMessageContentSegments(message);
    const layout = buildStreamingFlowLayout(segments, messageManager, { markupByKey: cached.segmentMarkupByKey, signatureByKey: cached.segmentSignatureByKey });
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
