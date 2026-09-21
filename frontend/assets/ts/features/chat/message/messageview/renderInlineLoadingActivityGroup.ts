/* SoAI - Chat feature render inline loading activity group [frontend/assets/ts/features/chat/message/messageview/renderInlineLoadingActivityGroup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { isString } from '@core/typeGuards.ts';
import { resolveChatStreamServerErrorMessage } from '@features/chat/chatstreamservice/streamErrorPresentation.ts';
import type { InlineLoadingActivitySegment } from '@features/chat/message/messageSegments.ts';
import { compactQueryWhitespace } from '@features/chat/toolactivity/payloadTextParsing.ts';
import { renderInlineStatusActivityLifecycleKeyAttribute } from '@features/chat/message/inlineStatusActivityIdentity.ts';
import { renderInlineActivityDuration, resolveInlineActivityDurationArguments } from '@features/chat/message/messageview/inlineActivityDuration.ts';
import { renderInlineStatusDot, renderInlineStatusIcon } from '@features/chat/message/messageview/inlineActivityStatusRendering.ts';
import { renderInlineActivityHeaderRow, renderInlineActivityLeadingIcon, renderInlineActivityStreamedPreview } from '@features/chat/message/messageview/inlineActivityHeaderRow.ts';
import { resolveInlineActivityName } from '@features/chat/message/messageview/inlineActivityName.ts';
import { clampInlineLabel } from '@features/chat/message/messageview/inlineActivityText.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';
import { renderSettledActivityDurationAttribute, shouldAnimateSettledActivityDuration, shouldRenderActivityDuration } from '@features/chat/message/messageview/activityDurationDisplay.ts';

interface RenderInlineLoadingActivityGroupArguments {
    segment: InlineLoadingActivitySegment;
    displayStatus: 'running' | 'completed' | 'cancelled' | 'error';
    durationStatus?: 'running' | 'completed' | 'cancelled' | 'error';
    toggleEnabled: boolean;
    latestActivityName: string | null;
}

const renderInlineLoadingPreview = (host: ChatMessageRenderHost, inputArguments: RenderInlineLoadingActivityGroupArguments): string => {
    const segment = inputArguments.segment;
    const technicalReason = isString(segment.reason) ? compactQueryWhitespace(segment.reason) : '';
    const errorType = isString(segment.errorType) ? compactQueryWhitespace(segment.errorType) : '';
    const reason = errorType ? resolveChatStreamServerErrorMessage(technicalReason, errorType) : technicalReason;
    const detailText = [reason, errorType].filter((value) => value.length > 0).join(' · ');
    const previewText = detailText ? clampInlineLabel(detailText, 120) : (inputArguments.latestActivityName ?? i18n.t('chat.loading.modelPreview'));
    return renderInlineActivityStreamedPreview(host, { status: inputArguments.displayStatus, visible: previewText, latest: previewText });
};

const renderInlineLoadingActivityGroup = (host: ChatMessageRenderHost, inputArguments: RenderInlineLoadingActivityGroupArguments): string => {
    const statusClass = `inline-activity-status-${inputArguments.displayStatus}`;
    const durationStatus = inputArguments.durationStatus ?? inputArguments.displayStatus;
    const leadingIconHtml = renderInlineActivityLeadingIcon(host, { variant: 'hourglass', iconName: 'hourglass', options: { size: 8, strokeWidth: 1.5 } });
    const statusDotHtml = renderInlineStatusDot(host, inputArguments.displayStatus);
    const statusIconHtml = renderInlineStatusIcon(host, inputArguments.displayStatus, 'clock');
    const previewHtml = renderInlineLoadingPreview(host, inputArguments);
    const displayMode = host.getActivityDurationDisplayMode();
    const durationHtml = shouldRenderActivityDuration(displayMode, 'collapsed', durationStatus)
        ? renderInlineActivityDuration(
              host,
              {
                  ...resolveInlineActivityDurationArguments(inputArguments.segment, host.nowMs()),
                  status: durationStatus
              },
              { animateEntrance: shouldAnimateSettledActivityDuration(displayMode, durationStatus) }
          )
        : '';
    const headerHtml = renderInlineActivityHeaderRow(host, {
        tagName: 'div',
        leadingIconHtml,
        statusLedHtml: statusDotHtml,
        mainIconHtml: statusIconHtml,
        name: resolveInlineActivityName(inputArguments.segment),
        previewHtml,
        durationHtml,
        actionId: inputArguments.toggleEnabled ? 'chat:toggle-loading-activity-item' : undefined,
        requiresCallId: false,
        toggleEnabled: inputArguments.toggleEnabled
    });
    const lifecycleKeyAttr = renderInlineStatusActivityLifecycleKeyAttribute((value) => host.escapeAttribute(value), inputArguments.segment);
    const startedAtMs = inputArguments.segment.startedAtMs;
    const startedAtAttr = durationStatus === 'running' && typeof startedAtMs === 'number' && isEpochMsNumber(startedAtMs) ? ` data-started-at-ms="${host.escapeAttribute(String(startedAtMs))}"` : '';
    const settledDurationAttr = renderSettledActivityDurationAttribute((value) => host.escapeAttribute(value), durationStatus, inputArguments.segment.durationMs);
    return `<div class="inline-activity inline-activity-type-loading ${statusClass}" data-loading-stack="true" data-collapsed="true"${lifecycleKeyAttr}${startedAtAttr}${settledDurationAttr}>${headerHtml}</div>`;
};

export { renderInlineLoadingActivityGroup };
export type { RenderInlineLoadingActivityGroupArguments };
