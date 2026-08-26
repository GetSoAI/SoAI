/* SoAI - Chat feature render failure presentation [frontend/assets/ts/features/chat/message/messageview/renderFailurePresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ChatMessage } from '@features/chat/message/messageSegments.ts';
import { buildAssistantResponseMarkup } from '@features/chat/message/assistantResponseMarkup.ts';
import { renderMessageError } from '@features/chat/message/messageview/renderCallDetails.ts';
import { isAssistantMessageRole } from '@features/chat/message/messageRole.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';

type RenderFailurePresenter = {
    renderWithPreservedContent: (message: ChatMessage, error: Error, context: string) => string;
};

export const createRenderFailurePresenter = (dependencies: { renderHost: ChatMessageRenderHost; handleError: (error: Error, context: string, options?: { notify?: boolean; severity?: 'debug' | 'info' | 'warn' | 'error'; rethrow?: boolean }) => void; renderPreservedContentOnlyMarkup: (message: ChatMessage) => string; renderPreservedPlainTextMarkup: (message: ChatMessage) => string }): RenderFailurePresenter => {
    const reportedRenderErrorsByMessage = new WeakMap<ChatMessage, Set<string>>();

    const reportRenderFailure = (message: ChatMessage, error: Error, context: string): void => {
        const reportedErrors = reportedRenderErrorsByMessage.get(message) ?? new Set<string>();
        if (reportedErrors.has(context)) {
            return;
        }
        reportedErrors.add(context);
        reportedRenderErrorsByMessage.set(message, reportedErrors);
        dependencies.handleError(error, context, { notify: false, severity: 'error' });
    };

    const renderMessageRenderErrorWithPreservedContent = (message: ChatMessage, errorText: string, context: string): string => {
        const errorHtml = renderMessageError(dependencies.renderHost, errorText);
        let preservedContent = '';
        try {
            preservedContent = dependencies.renderPreservedContentOnlyMarkup(message);
        } catch (error) {
            reportRenderFailure(message, ensureError(error), `${context}:preserved content`);
            preservedContent = dependencies.renderPreservedPlainTextMarkup(message);
        }

        if (!isAssistantMessageRole(message)) {
            return `${preservedContent}${errorHtml}`;
        }
        return buildAssistantResponseMarkup({
            bodyHtml: `${preservedContent}${errorHtml}`
        });
    };

    const renderWithPreservedContent = (message: ChatMessage, error: Error, context: string): string => {
        const runtimeError = ensureError(error);
        const errorText = i18n.t('chat.message.renderFailed');
        reportRenderFailure(message, runtimeError, context);
        return renderMessageRenderErrorWithPreservedContent(message, errorText, context);
    };

    return { renderWithPreservedContent };
};
