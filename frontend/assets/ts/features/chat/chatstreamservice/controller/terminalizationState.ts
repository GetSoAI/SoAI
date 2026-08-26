/* SoAI - Chat stream terminalization state controller [frontend/assets/ts/features/chat/chatstreamservice/controller/terminalizationState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { raceWithAbortSignal } from '@core/errors/abort.ts';
import type { ChatStreamingControllerContext, ConversationStreamState } from '@features/chat/chatstreamservice/controller/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const clearConversationTerminalizationPromiseState = (state: ConversationStreamState): void => {
    state.terminalizationPromise = null;
    state.terminalizationPromiseKey = null;
    state.terminalizationResolve = null;
    state.terminalizationReject = null;
};

const resolveConversationTerminalizationPromise = (context: ChatStreamingControllerContext, conversationId: string): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    if (!state || state.terminalizationResolve === null) {
        return;
    }
    const resolve = state.terminalizationResolve;
    clearConversationTerminalizationPromiseState(state);
    resolve();
};

const resolveAllConversationTerminalizationPromises = (context: ChatStreamingControllerContext): void => {
    for (const state of context.streamStateByConversationId.values()) {
        const resolve = state.terminalizationResolve;
        if (resolve === null) {
            continue;
        }
        clearConversationTerminalizationPromiseState(state);
        resolve();
    }
};

const resetConversationTerminalization = (context: ChatStreamingControllerContext, conversationId: string): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return;
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    if (!state) {
        return;
    }
    if (state.terminalRenderTimerId !== null) {
        context.timers.clearTimeout(state.terminalRenderTimerId);
        state.terminalRenderTimerId = null;
        state.terminalRenderToken += 1;
    }
    resolveConversationTerminalizationPromise(context, normalizedConversationId);
    state.terminalizationKey = null;
    state.terminalRenderSettled = false;
};

const waitForTerminalReconciliation = async (context: ChatStreamingControllerContext, conversationId: string, signal?: AbortSignal | null): Promise<void> => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        throw new Error('Chat stream terminal reconciliation requires a valid conversation id.');
    }
    const state = context.streamStateByConversationId.get(normalizedConversationId);
    const terminalizationPromise = state?.terminalizationPromise ?? null;
    if (state !== undefined && state.terminalRenderTimerId !== null && terminalizationPromise === null) {
        throw new Error('Chat stream terminal reconciliation is pending without a completion promise.');
    }
    if (terminalizationPromise === null) {
        return;
    }
    if (signal) {
        await raceWithAbortSignal(terminalizationPromise, signal);
        return;
    }
    await terminalizationPromise;
};

export { clearConversationTerminalizationPromiseState, resetConversationTerminalization, resolveAllConversationTerminalizationPromises, resolveConversationTerminalizationPromise, waitForTerminalReconciliation };
