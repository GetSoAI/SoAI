/* SoAI - Chat feature loading activity error text [frontend/assets/ts/features/chat/assistanteventtimeline/loadingActivityErrorText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveLatestLoadingActivityFromMessage } from '@features/chat/assistanteventtimeline/activityState.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveChatStreamServerErrorMessage } from '@features/chat/chatstreamservice/streamErrorPresentation.ts';

const resolveLoadingActivityErrorText = (message: ChatMessage): string | null => {
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

export { resolveLoadingActivityErrorText };
