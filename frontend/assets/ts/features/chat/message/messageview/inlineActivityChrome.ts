/* SoAI - Shared inline activity chrome rendering [frontend/assets/ts/features/chat/message/messageview/inlineActivityChrome.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsNumber } from '@core/time/epochMs.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { renderInlineActivityDuration, resolveInlineActivityDurationArguments } from '@features/chat/message/messageview/inlineActivityDuration.ts';
import { renderInlineActivityPreview } from '@features/chat/message/messageview/inlineActivityHeaderRow.ts';
import { renderInlineStatusDot, renderInlineStatusIcon } from '@features/chat/message/messageview/inlineActivityStatusRendering.ts';
import type { ChatMessageRenderHost, InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineThinkingActivitySegment, InlineToolActivitySegment, InlineWaitForUserActivitySegment } from '@features/chat/message/messageview/types.ts';
import { renderSettledActivityDurationAttribute, shouldAnimateSettledActivityDuration, shouldRenderActivityDuration, type ChatActivityDurationExpansionState } from '@features/chat/message/messageview/activityDurationDisplay.ts';

type InlineActivityChromeSegment = InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment | InlineThinkingActivitySegment | InlineToolActivitySegment;

type InlineActivityChrome = {
    statusClass: string;
    statusDotHtml: string;
    mainIconHtml: string;
    durationHtml: string;
    previewHtml: string;
    startedAtAttr: string;
    settledDurationAttr: string;
};

const renderInlinePreviewIfPresent = (host: ChatMessageRenderHost, text: string): string => {
    return text ? renderInlineActivityPreview(host, { text }) : '';
};

const renderInlineActivityChrome = (
    host: ChatMessageRenderHost,
    inputArguments: {
        segment: InlineActivityChromeSegment;
        defaultIconName?: IconName | undefined;
        mainIconHtml?: string | undefined;
        previewHtml?: string | undefined;
        previewText?: string | undefined;
        expansionState: ChatActivityDurationExpansionState;
    }
): InlineActivityChrome => {
    const mainIconHtml = inputArguments.mainIconHtml ?? renderInlineStatusIcon(host, inputArguments.segment.status, inputArguments.defaultIconName ?? 'plugin');
    const previewHtml = inputArguments.previewHtml ?? renderInlinePreviewIfPresent(host, inputArguments.previewText ?? '');
    const startedAtMs = inputArguments.segment.startedAtMs;
    const displayMode = host.getActivityDurationDisplayMode();
    return {
        statusClass: `inline-activity-status-${inputArguments.segment.status}`,
        statusDotHtml: renderInlineStatusDot(host, inputArguments.segment.status),
        mainIconHtml,
        durationHtml: shouldRenderActivityDuration(displayMode, inputArguments.expansionState, inputArguments.segment.status) ? renderInlineActivityDuration(host, resolveInlineActivityDurationArguments(inputArguments.segment, host.nowMs()), { animateEntrance: shouldAnimateSettledActivityDuration(displayMode, inputArguments.segment.status) }) : '',
        previewHtml,
        startedAtAttr: typeof startedAtMs === 'number' && isEpochMsNumber(startedAtMs) ? ` data-started-at-ms="${host.escapeAttribute(String(startedAtMs))}"` : '',
        settledDurationAttr: renderSettledActivityDurationAttribute((value) => host.escapeAttribute(value), inputArguments.segment.status, inputArguments.segment.durationMs)
    };
};

export { renderInlineActivityChrome };
export type { InlineActivityChrome };
