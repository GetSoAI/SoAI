/* SoAI - Chat stream terminalization error type [frontend/assets/ts/features/chat/chatstreamservice/controller/terminalizationError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class ChatStreamTerminalizationError extends Error {
    readonly conversationId: string;
    readonly terminalizationError: Error;
    #reported = false;

    constructor(conversationId: string, terminalizationError: Error) {
        super(`Chat stream terminalization failed: ${terminalizationError.message}`);
        this.name = 'ChatStreamTerminalizationError';
        this.conversationId = conversationId;
        this.terminalizationError = terminalizationError;
    }

    claimReport(): boolean {
        if (this.#reported) {
            return false;
        }
        this.#reported = true;
        return true;
    }
}

const reportChatStreamTerminalizationFailureOnce = (error: Error, reportFailure: (error: Error) => void): boolean => {
    if (!(error instanceof ChatStreamTerminalizationError)) {
        return false;
    }
    if (error.claimReport()) {
        reportFailure(error);
    }
    return true;
};

export { ChatStreamTerminalizationError, reportChatStreamTerminalizationFailureOnce };
