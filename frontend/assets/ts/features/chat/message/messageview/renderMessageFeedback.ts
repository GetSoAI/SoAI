/* SoAI - Chat feature render message feedback [frontend/assets/ts/features/chat/message/messageview/renderMessageFeedback.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveLoadingActivityErrorExplanationText, resolveLoadingActivityErrorText } from '@features/chat/assistanteventtimeline/loadingActivityErrorText.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { resolveAssistantOutputNoticeText } from '@features/chat/message/assistantOutputNotice.ts';
import { renderMessageError, renderMessageOutputNotice } from '@features/chat/message/messageview/renderCallDetails.ts';
import type { ChatMessageRenderHost } from '@features/chat/message/messageview/types.ts';

const renderMessageFeedback = (host: ChatMessageRenderHost, message: ChatMessage): string => {
    const errorText = resolveLoadingActivityErrorText(message);
    if (errorText) {
        const terminal = message.assistantEventTimeline?.findLast((event) => event.eventType === 'error');
        const providerError = isJsonObject(terminal?.payload.details) && typeof terminal.payload.details['upstream_failure_type'] === 'string';
        return renderMessageError(host, errorText, resolveLoadingActivityErrorExplanationText(message), providerError);
    }
    const notice = resolveAssistantOutputNoticeText(message);
    return notice ? renderMessageOutputNotice(host, notice) : '';
};

export { renderMessageFeedback };
