/* SoAI - Chat feature loading activity error text [frontend/assets/ts/features/chat/assistanteventtimeline/loadingActivityErrorText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveLatestLoadingActivityFromMessage } from '@features/chat/assistanteventtimeline/activityState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveChatStreamServerErrorMessage, resolveProviderExplanationText } from '@features/chat/chatstreamservice/streamErrorPresentation.ts';

const resolveLoadingActivityErrorText = (message: ChatMessage): string | null => {
    const timeline = message.assistantEventTimeline ?? [];
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const event = timeline[index];
        if (event?.eventType === 'error' && event.payload.message) {
            return resolveChatStreamServerErrorMessage(event.payload.message, event.payload.code ?? '', event.payload.details, event.payload['param'], true);
        }
    }
    const loadingActivity = resolveLatestLoadingActivityFromMessage(message);
    if (loadingActivity === null || loadingActivity.status !== 'error') {
        return null;
    }
    const reason = loadingActivity.reason;
    if (typeof reason !== 'string') {
        return null;
    }
    const trimmed = reason.trim();
    if (!trimmed) {
        return null;
    }
    return resolveChatStreamServerErrorMessage(trimmed, loadingActivity.errorType ?? '');
};

const resolveLoadingActivityErrorExplanationText = (message: ChatMessage): string | null => {
    const timeline = message.assistantEventTimeline ?? [];
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const event = timeline[index];
        if (event?.eventType === 'error') {
            return resolveProviderExplanationText(event.payload.explanation);
        }
    }
    return null;
};

export { resolveLoadingActivityErrorExplanationText, resolveLoadingActivityErrorText };
