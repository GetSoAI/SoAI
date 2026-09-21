/* SoAI - Chat feature render message text content [frontend/assets/ts/features/chat/message/messageview/renderMessageTextContent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isArray } from '@core/typeGuards.ts';
import { resolveLoadingActivityErrorText } from '@features/chat/assistanteventtimeline/loadingActivityErrorText.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveLoadingActivityToggleEnabled } from '@features/chat/message/messageview/loadingActivityToggleEnabled.ts';
import type { MessageSegment } from '@features/chat/message/messageSegments.ts';
import { buildAssistantResponseMarkup } from '@features/chat/message/assistantResponseMarkup.ts';
import { shouldCollapseLoadingActivities } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { renderCollapsedLoadingSummary, type CollapsedLoadingSummaryDependencies } from '@features/chat/message/messageview/collapsedLoadingSummaryRendering.ts';
import type { MessageRenderOptions, RenderedMessageTextContent } from '@features/chat/message/messageview/types.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';

interface RenderMessageTextContentDependencies extends CollapsedLoadingSummaryDependencies {
    isShowActivitiesEnabled: () => boolean;
    getCurrentConversationId: () => string | null;
    resolveMessageContentSegments: (message: ChatMessage) => MessageSegment[];
    getPreRenderedAssistantBodyHtml: (message: ChatMessage) => string | null;
    getLoadingActivityCollapsedState: (message: ChatMessage) => boolean | null;
    renderSegmentsWithOptions: (segments: MessageSegment[], options?: MessageRenderOptions) => string;
    renderAssistantActivityWidgets: (segments: readonly MessageSegment[]) => string;
    renderMessageErrorMarkup: (errorText: string) => string;
    handleMessageRenderError: (message: ChatMessage, error: Error, context: string) => string;
}

const resolveLoadingActivitiesCollapsed = (dependencies: RenderMessageTextContentDependencies, message: ChatMessage): boolean => {
    return shouldCollapseLoadingActivities({
        isShowActivitiesEnabled: dependencies.isShowActivitiesEnabled(),
        collapsedOverride: dependencies.getLoadingActivityCollapsedState(message)
    });
};

const createMessageRenderOptions = (dependencies: RenderMessageTextContentDependencies, normalizedRole: string, enableLoadingActivityToggle: boolean = false): MessageRenderOptions => {
    const conversationId = dependencies.getCurrentConversationId();
    const isUserMessage = normalizedRole === 'user';
    if (enableLoadingActivityToggle) {
        return {
            hideDefaultImageLabel: isUserMessage,
            compactAttachmentCards: isUserMessage,
            conversationId,
            loadingActivityToggleAction: 'chat:toggle-loading-activity-item',
            loadingActivityToggleEnabled: true
        };
    }
    return {
        hideDefaultImageLabel: isUserMessage,
        compactAttachmentCards: isUserMessage,
        conversationId,
        loadingActivityToggleEnabled: false
    };
};

const shouldUsePreRenderedAssistantBody = (dependencies: RenderMessageTextContentDependencies, message: ChatMessage): boolean => {
    return !resolveLoadingActivitiesCollapsed(dependencies, message);
};

const isAssistantWidgetRenderReady = (presentation: ChatMessageRenderPresentation, forceSettledAssistantBody: boolean): boolean => {
    if (forceSettledAssistantBody) {
        return true;
    }
    return !presentation.isActiveStreamingAssistant;
};

const renderSegmentsWithLoadingGroup = (dependencies: RenderMessageTextContentDependencies, message: ChatMessage, segments: MessageSegment[], presentation: ChatMessageRenderPresentation): string => {
    if (presentation.normalizedRole !== 'assistant') {
        return dependencies.renderSegmentsWithOptions(segments, createMessageRenderOptions(dependencies, presentation.normalizedRole, resolveLoadingActivityToggleEnabled(segments)));
    }
    if (resolveLoadingActivitiesCollapsed(dependencies, message) === true) {
        return renderCollapsedLoadingSummary(dependencies, message, segments, presentation);
    }
    return dependencies.renderTimelineSegmentsMarkup(segments);
};

const renderMessageTextContent = (dependencies: RenderMessageTextContentDependencies, message: ChatMessage, presentation: ChatMessageRenderPresentation, segments: MessageSegment[] | null = null, options: { forceSettledAssistantBody?: boolean } = {}): RenderedMessageTextContent => {
    const forceSettledAssistantBody = options.forceSettledAssistantBody === true;
    if (presentation.normalizedRole === 'assistant' && !forceSettledAssistantBody) {
        if (shouldUsePreRenderedAssistantBody(dependencies, message)) {
            const preRendered = dependencies.getPreRenderedAssistantBodyHtml(message);
            if (preRendered !== null) {
                return { html: buildAssistantResponseMarkup({ bodyHtml: preRendered }), resolvedSegments: null };
            }
        }
    }

    let resolvedSegments: MessageSegment[];
    try {
        resolvedSegments = isArray(segments) ? segments : dependencies.resolveMessageContentSegments(message);
    } catch (error) {
        const runtimeError = ensureError(error);
        const failure = { html: dependencies.handleMessageRenderError(message, runtimeError, 'chat:resolveMessageContentSegments'), resolvedSegments: null };
        return failure;
    }

    try {
        const errorText = resolveLoadingActivityErrorText(message);
        const contentHtml = renderSegmentsWithLoadingGroup(dependencies, message, resolvedSegments, presentation);
        const errorHtml = errorText ? dependencies.renderMessageErrorMarkup(errorText) : '';

        if (presentation.normalizedRole !== 'assistant') {
            return { html: `${contentHtml}${errorHtml}`, resolvedSegments };
        }

        const widgetsHtml = isAssistantWidgetRenderReady(presentation, forceSettledAssistantBody) ? dependencies.renderAssistantActivityWidgets(resolvedSegments) : '';
        return { html: buildAssistantResponseMarkup({ bodyHtml: `${contentHtml}${widgetsHtml}${errorHtml}` }), resolvedSegments };
    } catch (error) {
        const runtimeError = ensureError(error);
        const failure = { html: dependencies.handleMessageRenderError(message, runtimeError, 'chat:renderMessageSegments'), resolvedSegments };
        return failure;
    }
};

export { renderMessageTextContent };
