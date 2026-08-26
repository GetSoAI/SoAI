/* SoAI - Stale-guard helpers for chat render worker responses [frontend/assets/ts/features/chat/message/renderworkers/renderContextGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RenderContext } from '@features/chat/messagerenderworker/protocol.ts';

type WorkerRenderContextGuardDependencies = {
    getWorkerRenderEpoch: () => number;
    getCurrentConversationId: () => string | null;
};

const isWorkerRenderContextCurrent = (dependencies: WorkerRenderContextGuardDependencies, inputArguments: { expected: RenderContext; messageDomId: string; messageRevision: number; stateSignature?: string | null; signal: AbortSignal | null }): boolean => {
    if (inputArguments.signal?.aborted) {
        return false;
    }
    if (dependencies.getWorkerRenderEpoch() !== inputArguments.expected.epoch) {
        return false;
    }
    if (dependencies.getCurrentConversationId() !== inputArguments.expected.conversationId) {
        return false;
    }
    if (inputArguments.expected.messageDomId !== inputArguments.messageDomId) {
        return false;
    }
    if (inputArguments.expected.messageRevision !== inputArguments.messageRevision) {
        return false;
    }
    if (typeof inputArguments.stateSignature === 'string' && inputArguments.expected.stateSignature !== inputArguments.stateSignature) {
        return false;
    }
    return true;
};

export { isWorkerRenderContextCurrent };
export type { WorkerRenderContextGuardDependencies };
