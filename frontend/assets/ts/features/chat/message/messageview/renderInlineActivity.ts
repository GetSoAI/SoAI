/* SoAI - Chat feature render inline activity [frontend/assets/ts/features/chat/message/messageview/renderInlineActivity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { compactQueryWhitespace } from '@features/chat/toolactivity/payloadTextParsing.ts';
import { renderInlineActivityChrome } from '@features/chat/message/messageview/inlineActivityChrome.ts';
import { renderInlineStatusActivityLifecycleKeyAttribute } from '@features/chat/message/inlineStatusActivityIdentity.ts';
import { renderInlineToolActivityMarkup } from '@features/chat/message/messageview/inlineToolActivityMarkup.ts';
import { resolveInlineToolActivityPresentation } from '@features/chat/message/messageview/inlineToolActivityPresentation.ts';
import { renderMarkdownContent } from '@features/chat/message/messageview/renderMarkdown.ts';
import { THINKING_PREVIEW_ATTRIBUTE_NAMES, clampInlineLabel, formatThinkingPreviewLabel, resolveThinkingInitialPreview, resolveThinkingLatestCompletePreview } from '@features/chat/message/messageview/inlineActivityText.ts';
import { renderInlineActivityHeaderRow, renderInlineActivityLeadingIcon, renderInlineActivityPreview } from '@features/chat/message/messageview/inlineActivityHeaderRow.ts';
import type { ChatMessageRenderHost, InlineActionUpdateSegment, InlineLoadingActivitySegment, InlineProcessingActivitySegment, InlineThinkingActivitySegment, InlineToolActivitySegment, InlineWaitForUserActivitySegment, MessageRenderOptions } from '@features/chat/message/messageview/types.ts';
import { INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE, INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE } from '@features/chat/message/inlineActivityDetailsIdentity.ts';
import { resolveInlineActivityDetailsSignature } from '@features/chat/message/messageSegmentSignatures.ts';

const HOURGLASS_LEADING_ICON_SIZE_PX = 8;

const renderInlineSimpleActivity = (
    host: ChatMessageRenderHost,
    inputArguments: {
        segment: InlineLoadingActivitySegment | InlineProcessingActivitySegment | InlineWaitForUserActivitySegment;
        label: string;
        iconName: IconName;
        extraClassName: string;
        toggleAction?: string;
    }
): string => {
    const segment = inputArguments.segment;
    if (segment.status !== 'running' && segment.status !== 'completed' && segment.status !== 'cancelled' && segment.status !== 'error') {
        throw new Error('Inline activity has invalid status');
    }
    const leadingIconHtml = renderInlineActivityLeadingIcon(host, { variant: 'hourglass', iconName: 'hourglass', options: { size: HOURGLASS_LEADING_ICON_SIZE_PX, strokeWidth: 1.5 } });
    const reason = isString(segment.reason) ? compactQueryWhitespace(segment.reason) : '';
    const errorType = isString(segment.errorType) ? compactQueryWhitespace(segment.errorType) : '';
    const detailText = [reason, errorType].filter((value) => value.length > 0).join(' · ');
    const detailPreview = detailText ? clampInlineLabel(detailText, 120) : inputArguments.extraClassName === 'inline-activity-type-loading' ? i18n.t('chat.loading.modelPreview') : '';
    const chrome = renderInlineActivityChrome(host, { segment, defaultIconName: inputArguments.iconName, previewText: detailPreview, expansionState: 'collapsed' });
    const headerHtml = renderInlineActivityHeaderRow(host, {
        tagName: 'div',
        leadingIconHtml,
        statusLedHtml: chrome.statusDotHtml,
        mainIconHtml: chrome.mainIconHtml,
        name: inputArguments.label,
        previewHtml: chrome.previewHtml,
        durationHtml: chrome.durationHtml,
        actionId: inputArguments.toggleAction,
        requiresCallId: false,
        toggleEnabled: typeof inputArguments.toggleAction === 'string'
    });
    const activityClasses = `inline-activity ${inputArguments.extraClassName} ${chrome.statusClass}`;
    const lifecycleKeyAttr = renderInlineStatusActivityLifecycleKeyAttribute((value) => host.escapeAttribute(value), segment);
    return `<div class="${activityClasses}" data-collapsed="true"${lifecycleKeyAttr}${chrome.startedAtAttr}${chrome.settledDurationAttr}>${headerHtml}</div>`;
};
const renderInlineActionUpdate = (host: ChatMessageRenderHost, segment: InlineActionUpdateSegment): string => {
    const content = segment.text.trim();
    if (!content) {
        throw new Error(`Inline action update text is required for call id: ${segment.callId}`);
    }
    const inlineActionUpdateClass = 'inline-action-update';
    const contentHtml = renderMarkdownContent(host, content);
    return `<div class="${inlineActionUpdateClass}" data-call-id="${host.escapeAttribute(segment.callId)}" data-timeline-sequence-index="${host.escapeAttribute(String(segment.timelineSequenceIndex))}"><div class="inline-action-update-text">${contentHtml}</div></div>`;
};
const renderThinkingHeaderQuery = (host: ChatMessageRenderHost, status: 'running' | 'completed' | 'cancelled' | 'error', text: string): string => {
    const initialPreview = resolveThinkingInitialPreview(text);
    const latestCompletePreview = resolveThinkingLatestCompletePreview(text);
    const visiblePreview = status === 'running' ? initialPreview : latestCompletePreview || initialPreview;
    const visibleLabel = formatThinkingPreviewLabel(visiblePreview);
    const visibleAttribute = visibleLabel;
    const latestAttribute = formatThinkingPreviewLabel(latestCompletePreview);
    const rootAttributes = `${THINKING_PREVIEW_ATTRIBUTE_NAMES.root}="true"` + ` ${THINKING_PREVIEW_ATTRIBUTE_NAMES.status}="${host.escapeAttribute(status)}"` + ` ${THINKING_PREVIEW_ATTRIBUTE_NAMES.visible}="${host.escapeAttribute(visibleAttribute)}"` + ` ${THINKING_PREVIEW_ATTRIBUTE_NAMES.latest}="${host.escapeAttribute(latestAttribute)}"`;
    return renderInlineActivityPreview(host, { text: visibleLabel, rootAttributes });
};

const renderThinkingDetailsContent = (host: ChatMessageRenderHost, content: string): string => {
    if (!host.isRichTextEnabled()) {
        const escaped = host.escapeHtml(content);
        return `<p>${escaped.replace(/\n/g, '<br>')}</p>`;
    }
    return host.renderRichText(content, (descriptor) => {
        const escaped = host.escapeHtml(descriptor.value);
        return `<pre class="code-block-plain"><code>${escaped}</code></pre>`;
    });
};

const renderInlineThinkingDetails = (host: ChatMessageRenderHost, segment: InlineThinkingActivitySegment, detailsSignature: string = resolveInlineActivityDetailsSignature({ ...segment, collapsed: false }, host.nowMs())): string => {
    const contentHtml = segment.text.trim().length > 0 ? renderThinkingDetailsContent(host, segment.text) : '<p></p>';
    const scrollKey = `thinking:${segment.callId}:details`;
    return `<div class="inline-activity-details" ${INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE}="${host.escapeAttribute(detailsSignature)}" data-scroll-key="${host.escapeAttribute(scrollKey)}"><div class="message-thinking-phase">${contentHtml}</div></div>`;
};

const renderInlineThinkingActivity = (host: ChatMessageRenderHost, segment: InlineThinkingActivitySegment): string => {
    const openRequested = segment.collapsed === false;
    const resolvedStatus = segment.status;
    if (resolvedStatus !== 'running' && resolvedStatus !== 'completed' && resolvedStatus !== 'cancelled' && resolvedStatus !== 'error') {
        throw new Error(`Invalid inline thinking status for call id: ${segment.callId}`);
    }

    const leadingIconHtml = renderInlineActivityLeadingIcon(host, { variant: 'expander', iconName: 'chevron-right', options: { size: 10, strokeWidth: 4 } });
    const label = i18n.t('chat.thinking.label');
    const chrome = renderInlineActivityChrome(host, {
        segment,
        defaultIconName: 'thinking',
        previewHtml: renderThinkingHeaderQuery(host, resolvedStatus, segment.text),
        expansionState: openRequested ? 'expanded' : 'collapsed'
    });

    const detailsSignature = resolveInlineActivityDetailsSignature({ ...segment, collapsed: false }, host.nowMs());
    const openRequestedAttr = openRequested ? ` ${INLINE_ACTIVITY_DETAILS_OPEN_REQUESTED_ATTRIBUTE}="true"` : '';

    const headerHtml = renderInlineActivityHeaderRow(host, {
        tagName: 'div',
        leadingIconHtml,
        statusLedHtml: chrome.statusDotHtml,
        mainIconHtml: chrome.mainIconHtml,
        name: label,
        previewHtml: chrome.previewHtml,
        durationHtml: chrome.durationHtml,
        actionId: 'chat:toggle-tool-activity-item',
        callId: segment.callId,
        toggleEnabled: true,
        expandedCloseButton: true
    });
    return `<div class="inline-activity ${chrome.statusClass} inline-activity-type-thinking" data-call-id="${host.escapeAttribute(segment.callId)}" data-timeline-sequence-index="${host.escapeAttribute(String(segment.timelineSequenceIndex))}" ${INLINE_ACTIVITY_DETAILS_SIGNATURE_ATTRIBUTE}="${host.escapeAttribute(detailsSignature)}"${openRequestedAttr} data-collapsed="true"${chrome.startedAtAttr}${chrome.settledDurationAttr}>${headerHtml}</div>`;
};
const renderInlineToolActivity = (host: ChatMessageRenderHost, segment: InlineToolActivitySegment): string => {
    const presentation = resolveInlineToolActivityPresentation(segment);
    const detailsSignature = resolveInlineActivityDetailsSignature({ ...segment, collapsed: false }, host.nowMs());
    return renderInlineToolActivityMarkup(host, segment, {
        presentation,
        detailsSignature
    });
};

const renderInlineLoadingActivity = (host: ChatMessageRenderHost, segment: InlineLoadingActivitySegment, options: MessageRenderOptions = {}): string => {
    const toggleEnabled = typeof options.loadingActivityToggleEnabled === 'boolean' ? options.loadingActivityToggleEnabled : host.isShowActivitiesEnabled();
    const toggleAction = toggleEnabled ? (typeof options.loadingActivityToggleAction === 'string' ? options.loadingActivityToggleAction : 'chat:toggle-loading-activity-item') : undefined;
    return renderInlineSimpleActivity(host, {
        segment,
        label: i18n.t('chat.loading.label'),
        iconName: 'clock',
        extraClassName: 'inline-activity-type-loading',
        ...(typeof toggleAction === 'string' ? { toggleAction } : {})
    });
};

const renderInlineProcessingActivity = (host: ChatMessageRenderHost, segment: InlineProcessingActivitySegment): string => {
    return renderInlineSimpleActivity(host, {
        segment,
        label: i18n.t('chat.processing.label'),
        iconName: 'hardware',
        extraClassName: 'inline-activity-type-processing'
    });
};

const renderInlineWaitForUserActivity = (host: ChatMessageRenderHost, segment: InlineWaitForUserActivitySegment): string => {
    return renderInlineSimpleActivity(host, {
        segment,
        label: i18n.t('chat.waitForUser.label'),
        iconName: 'clock',
        extraClassName: 'inline-activity-type-wait-for-user'
    });
};

export { renderInlineActionUpdate, renderInlineLoadingActivity, renderInlineProcessingActivity, renderInlineThinkingActivity, renderInlineToolActivity, renderInlineWaitForUserActivity, renderInlineThinkingDetails };
