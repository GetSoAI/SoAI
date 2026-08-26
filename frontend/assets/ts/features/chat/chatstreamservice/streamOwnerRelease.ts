/* SoAI - Chat stream owner release policy [frontend/assets/ts/features/chat/chatstreamservice/streamOwnerRelease.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPageTerminating } from '@core/lifecycle/pageTermination.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';

const markChatStreamOwnerReleaseRequested = (session: ChatStreamSession): void => {
    if (session.transportMode !== 'owner') {
        return;
    }
    session.ownerReleaseRequested = true;
    session.ownerReleaseListener?.();
};

const bindChatStreamOwnerRelease = (session: ChatStreamSession, listener: () => void): (() => void) => {
    if (session.ownerReleaseListener !== null) {
        throw new Error('Chat stream owner release listener is already bound');
    }
    session.ownerReleaseListener = listener;
    if (session.ownerReleaseRequested) listener();
    return (): void => {
        if (session.ownerReleaseListener === listener) session.ownerReleaseListener = null;
    };
};

const shouldReleaseChatStreamOwnerLocally = (session: ChatStreamSession): boolean => {
    if (session.transportMode !== 'owner') {
        return false;
    }
    if (session.pendingCancellation !== null) {
        return false;
    }
    return session.ownerReleaseRequested || isPageTerminating();
};

const releaseChatStreamOwnerLocally = (session: ChatStreamSession, markDone: () => void): void => {
    session.ownerReleaseRequested = true;
    markDone();
};

export { bindChatStreamOwnerRelease, markChatStreamOwnerReleaseRequested, releaseChatStreamOwnerLocally, shouldReleaseChatStreamOwnerLocally };
