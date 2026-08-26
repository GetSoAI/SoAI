/* SoAI - Conversation export inline multimedia preparation [frontend/assets/ts/features/chat/conversationexport/inlineMedia.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonApiClient } from '@core/api/jsonRequestGate.ts';
import { ChatInlineMultimediaEnhancer } from '@features/chat/message/enhancers/ChatInlineMultimediaEnhancer.ts';
import { createInlineMultimediaPreviewFeedbackRecorder } from '@features/chat/message/enhancers/inlineMultimediaPreviewFeedback.ts';

const enhanceConversationExportInlineMedia = async (inputArguments: { apiClient: JsonApiClient; container: HTMLElement; conversationId: string }): Promise<void> => {
    const enhancer = new ChatInlineMultimediaEnhancer({
        apiClient: inputArguments.apiClient,
        notifyDomChanged: () => {}
    });
    try {
        await enhancer.enhance(inputArguments.container, inputArguments.conversationId, createInlineMultimediaPreviewFeedbackRecorder(null), {
            allowImplicitRemoteUrlCards: false
        });
    } finally {
        enhancer.dispose();
    }
};

export { enhanceConversationExportInlineMedia };
