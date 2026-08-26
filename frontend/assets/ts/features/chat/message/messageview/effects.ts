/* SoAI - Chat feature message view effects [frontend/assets/ts/features/chat/message/messageview/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { safeJsonStringify } from '@core/serialization/json.ts';
import { isArray } from '@core/typeGuards.ts';
import { injectAssistantBodyRootAttributes } from '@features/chat/message/assistantBodyRootAttributes.ts';
import { buildTimelineRenderItems } from '@features/chat/message/messageTimelineRenderItems.ts';
import { isInlineDetailsSegment } from '@features/chat/message/messageSegmentTypes.ts';
import { renderToolCall } from '@features/chat/message/messageview/renderCallDetails.ts';
import { renderImageFigure } from '@features/chat/message/messageview/renderImageFigure.ts';
import { renderInlineActionUpdate, renderInlineLoadingActivity, renderInlineProcessingActivity, renderInlineThinkingActivity, renderInlineThinkingDetails, renderInlineToolActivity, renderInlineWaitForUserActivity } from '@features/chat/message/messageview/renderInlineActivity.ts';
import { renderInlineToolDetails } from '@features/chat/message/messageview/inlineToolActivityDetails.ts';
import { renderMarkdownContent } from '@features/chat/message/messageview/renderMarkdown.ts';
import { isAttachmentSummarySegment, renderAttachmentCard, renderAttachmentStrip } from '@features/chat/message/messageview/attachmentSummaryCards.ts';
import { resolveImageSegment, resolveSegmentText } from '@features/chat/message/messageview/mappers.ts';
import { createLoadingActivityToggleSegmentResolver } from '@features/chat/message/messageview/loadingActivityToggleEnabled.ts';
import type { ChatMessageRenderHost, ImageSegment, MessageRenderOptions, MessageSegment } from '@features/chat/message/messageview/types.ts';

const renderImageContent = (host: ChatMessageRenderHost, segment: ImageSegment, options: MessageRenderOptions = {}): string => {
    const resolvedImage = resolveImageSegment(segment, options.hideDefaultImageLabel === true);
    if (resolvedImage === null) {
        return '';
    }
    return renderImageFigure(host, {
        src: resolvedImage.src,
        label: resolvedImage.label,
        allowEmptyLabel: options.hideDefaultImageLabel === true,
        className: 'message-image',
        downloadName: 'soai-image.png'
    });
};

const renderTimelineMarkup = (host: ChatMessageRenderHost, segments: MessageSegment[], options: MessageRenderOptions = {}): string => {
    const result = buildTimelineRenderItems({
        segments,
        nowMs: host.nowMs(),
        renderSegment: (renderSegments, renderOptions) => renderSegmentsWithOptions(host, renderSegments, renderOptions),
        sortableTextTables: options.sortableTextTables === true
    });
    const parts: string[] = [];
    for (const item of result.items) {
        parts.push(injectAssistantBodyRootAttributes(host, item.markup, item.key, item.signature));
    }
    return parts.join('');
};

const renderSegment = (host: ChatMessageRenderHost, segment: MessageSegment, options: MessageRenderOptions = {}): string => {
    if (segment.type === 'text') {
        const resolved = resolveSegmentText(segment);
        return toTrimmedString(resolved.value) ? renderMarkdownContent(host, resolved.value, { sortableTables: options.sortableTextTables === true }) : '';
    }
    if (segment.type === 'image') {
        return renderImageContent(host, segment, options);
    }
    if (isAttachmentSummarySegment(segment)) {
        return renderAttachmentCard(host, segment, options);
    }
    if (segment.type === 'inline_tool_activity') {
        return renderInlineToolActivity(host, segment);
    }
    if (segment.type === 'inline_thinking_activity') {
        return renderInlineThinkingActivity(host, segment);
    }
    if (segment.type === 'inline_action_update') {
        return renderInlineActionUpdate(host, segment);
    }
    if (segment.type === 'inline_loading_activity') {
        return renderInlineLoadingActivity(host, segment, options);
    }
    if (segment.type === 'inline_processing_activity') {
        return renderInlineProcessingActivity(host, segment);
    }
    if (segment.type === 'inline_wait_for_user_activity') {
        return renderInlineWaitForUserActivity(host, segment);
    }
    if (segment.type === 'tool_call') {
        return renderToolCall(host, segment);
    }
    if (segment.type === 'thinking') {
        return '';
    }
    return renderMarkdownContent(host, safeJsonStringify(segment));
};

const renderInlineActivityDetails = (host: ChatMessageRenderHost, segment: MessageSegment): string => {
    if (!isInlineDetailsSegment(segment)) {
        return '';
    }
    return segment.type === 'inline_tool_activity' ? renderInlineToolDetails(host, segment, (segments) => renderTimelineMarkup(host, segments)) : renderInlineThinkingDetails(host, segment);
};

const renderSegmentsWithOptions = (host: ChatMessageRenderHost, segments: MessageSegment[], options: MessageRenderOptions = {}): string => {
    if (!isArray(segments) || segments.length === 0) {
        return '<p></p>';
    }

    const parts: string[] = [];
    const attachmentSegments = options.compactAttachmentCards === true ? segments.filter(isAttachmentSummarySegment) : [];
    const resolveLoadingActivityToggleForSegment = createLoadingActivityToggleSegmentResolver(options.loadingActivityToggleEnabled === true);

    for (const segment of segments) {
        if (!segment) {
            continue;
        }
        if (options.compactAttachmentCards === true && isAttachmentSummarySegment(segment)) {
            continue;
        }
        let renderOptions = options;
        if (segment.type === 'inline_loading_activity' && options.loadingActivityToggleEnabled === true) {
            renderOptions = {
                ...options,
                loadingActivityToggleEnabled: resolveLoadingActivityToggleForSegment(segment)
            };
        }
        const rendered = renderSegment(host, segment, renderOptions);
        if (rendered) {
            parts.push(rendered);
        }
    }

    if (attachmentSegments.length > 0) {
        parts.push(renderAttachmentStrip(host, attachmentSegments, options));
    }

    return parts.join('');
};

const renderSegments = (host: ChatMessageRenderHost, segments: MessageSegment[], options: MessageRenderOptions = {}): string => {
    return renderSegmentsWithOptions(host, segments, options);
};

export { renderInlineActivityDetails, renderSegments, renderTimelineMarkup };
