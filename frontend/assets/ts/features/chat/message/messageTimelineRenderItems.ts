/* SoAI - Chat feature message timeline render items [frontend/assets/ts/features/chat/message/messageTimelineRenderItems.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { resolveInlineActivityDetailsSignature, resolveTimelineBaseSegmentSignature } from '@features/chat/message/messageSegmentSignatures.ts';
import type { MessageRenderOptions } from '@features/chat/message/messageview/types.ts';
import { createLoadingActivityToggleSegmentResolver, resolveLoadingActivityToggleEnabled } from '@features/chat/message/messageview/loadingActivityToggleEnabled.ts';
import { resolveTimelineSegmentKey } from '@features/chat/message/messageTimelineSegmentKeys.ts';

type TimelineRenderItem = { key: string; signature: string; markup: string; textSource: string | null };
type TimelineRenderSegment = (segments: MessageSegment[], options: MessageRenderOptions) => string;
type ActiveTextSlot = { markup: string };
type ActiveTimelineTextRun = { key: string; text: string };

type TimelineRenderItemsResult = {
    activeTextRun: ActiveTimelineTextRun | null;
    items: TimelineRenderItem[];
};

const resolveInlineActivityShellSignature = (segment: MessageSegment, baseSignature: string, nowMs: number): string => {
    if ((segment.type === 'inline_tool_activity' || segment.type === 'inline_thinking_activity') && segment.collapsed === false) {
        return [baseSignature, resolveInlineActivityDetailsSignature({ ...segment, collapsed: false }, nowMs)].join('|');
    }
    return baseSignature;
};

const resolveActiveTextSegmentIndex = (segments: MessageSegment[]): number => {
    let activeIndex = -1;
    for (let index = 0; index < segments.length; index += 1) {
        const segment = segments[index];
        if (segment?.type === 'text' && segment.isStreamingActive === true) {
            if (activeIndex !== -1) {
                throw new Error('Timeline contains multiple active text segments');
            }
            activeIndex = index;
        }
    }
    return activeIndex;
};

const renderTimelineSegmentMarkup = (inputArguments: { segment: MessageSegment; key: string; renderTimeMs: number; renderSegment: TimelineRenderSegment; cache: { markupByKey: Map<string, string> | null; signatureByKey: Map<string, string> | null }; loadingActivityToggleEnabled: boolean; sortableTextTables: boolean }): TimelineRenderItem | null => {
    const baseSignature = resolveInlineActivityShellSignature(inputArguments.segment, resolveTimelineBaseSegmentSignature(inputArguments.segment, inputArguments.renderTimeMs), inputArguments.renderTimeMs);
    const interactionSignature = inputArguments.segment.type === 'text' ? [baseSignature, inputArguments.sortableTextTables ? 'sortable_tables' : 'static_tables'].join('|') : baseSignature;
    const signature = inputArguments.segment.type === 'inline_loading_activity' ? [interactionSignature, inputArguments.loadingActivityToggleEnabled ? 'toggle_enabled' : 'toggle_disabled'].join('|') : interactionSignature;
    const cachedSignature = inputArguments.cache.signatureByKey?.get(inputArguments.key) ?? null;
    const cachedMarkup = cachedSignature === signature ? (inputArguments.cache.markupByKey?.get(inputArguments.key) ?? null) : null;
    const fromCache = !!(cachedMarkup && cachedMarkup.trim().length > 0);
    const rendered = fromCache
        ? cachedMarkup
        : inputArguments.renderSegment([inputArguments.segment], {
              loadingActivityToggleEnabled: inputArguments.loadingActivityToggleEnabled,
              sortableTextTables: inputArguments.sortableTextTables
          });
    if (!rendered) {
        return null;
    }
    const markup = !fromCache && inputArguments.segment.type === 'text' ? `<div class="message-stream-text-block">${rendered}</div>` : rendered;
    return { key: inputArguments.key, signature, markup, textSource: inputArguments.segment.type === 'text' ? inputArguments.segment.value : null };
};

const buildTimelineRenderItems = (inputArguments: { segments: MessageSegment[]; renderSegment: TimelineRenderSegment; nowMs: number; cache?: { markupByKey: Map<string, string> | null; signatureByKey: Map<string, string> | null }; activeTextSlot?: ActiveTextSlot | null; sortableTextTables?: boolean }): TimelineRenderItemsResult => {
    const occurrences = new Map<string, number>();
    const items: TimelineRenderItem[] = [];
    const renderTimeMs = inputArguments.nowMs;
    const cache = inputArguments.cache ?? { markupByKey: null, signatureByKey: null };
    const activeTextSegmentIndex = inputArguments.activeTextSlot ? resolveActiveTextSegmentIndex(inputArguments.segments) : -1;
    const loadingActivityToggleEnabled = resolveLoadingActivityToggleEnabled(inputArguments.segments);
    const resolveLoadingActivityToggleForSegment = createLoadingActivityToggleSegmentResolver(loadingActivityToggleEnabled);
    let activeTextRun: ActiveTimelineTextRun | null = null;

    for (const [index, segment] of inputArguments.segments.entries()) {
        if (!segment) {
            continue;
        }
        const key = resolveTimelineSegmentKey(segment, index, occurrences);
        if (segment.type === 'text' && inputArguments.activeTextSlot && index === activeTextSegmentIndex) {
            activeTextRun = { key, text: segment.value };
            items.push({
                key,
                signature: 'stream_text_slot',
                markup: inputArguments.activeTextSlot.markup,
                textSource: segment.value
            });
            continue;
        }
        const item = renderTimelineSegmentMarkup({
            segment,
            key,
            renderTimeMs,
            renderSegment: inputArguments.renderSegment,
            cache,
            loadingActivityToggleEnabled: resolveLoadingActivityToggleForSegment(segment),
            sortableTextTables: inputArguments.sortableTextTables === true
        });
        if (item) {
            items.push(item);
        }
    }

    return { activeTextRun, items };
};

export { buildTimelineRenderItems };
export type { TimelineRenderItem };
