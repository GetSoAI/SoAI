/* SoAI - Chat feature render scheduling [frontend/assets/ts/features/chat/chatstreamservice/controller/renderScheduling.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { ChatStreamingControllerContext } from '@features/chat/chatstreamservice/controller/types.ts';

const scheduleConversationListRender = (context: ChatStreamingControllerContext, message: string): void => {
    if (context.disposed || !context.presentationActive) {
        return;
    }
    void context.dependencies.presentation.renderConversationList().catch((error) => {
        context.errorHandler?.debug?.('ChatStream', message, ensureError(error));
    });
};

const renderCurrentConversationSafely = async (context: ChatStreamingControllerContext, message: string): Promise<void> => {
    if (context.disposed || !context.presentationActive) {
        return;
    }
    try {
        await context.dependencies.presentation.renderCurrentConversation();
    } catch (error) {
        context.errorHandler?.debug?.('ChatStream', message, ensureError(error));
    }
};

const scheduleNotedConversationListRender = (context: ChatStreamingControllerContext, note: string): void => {
    scheduleConversationListRender(context, `Failed to render conversation list (${note})`);
};

export { renderCurrentConversationSafely, scheduleConversationListRender, scheduleNotedConversationListRender };
