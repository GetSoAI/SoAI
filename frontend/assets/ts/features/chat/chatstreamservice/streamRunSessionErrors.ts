/* SoAI - Chat feature stream run session errors [frontend/assets/ts/features/chat/chatstreamservice/streamRunSessionErrors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class ChatStreamFirstServerEventHookError extends Error {
    override readonly cause: Error;

    constructor(message: string, cause: Error) {
        super(message);
        this.name = 'ChatStreamFirstServerEventHookError';
        this.cause = cause;
    }
}

export { ChatStreamFirstServerEventHookError };
