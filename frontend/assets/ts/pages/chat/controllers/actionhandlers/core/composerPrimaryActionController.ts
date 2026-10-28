/* SoAI - Chat page composer primary action controller [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/composerPrimaryActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { sleepMsAbortable } from '@core/primitives/sleepMsAbortable.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { normalizeConversationId, type ChatComposerActionMode, type ChatTurnAdmissionSnapshot } from '@features/chat/public.ts';
import { collapseSidebarIfNarrowViewport, isCurrentConversationExecuting, runCollapsedUiTask } from '@pages/chat/controllers/actionhandlers/core/effects.ts';
import type { ChatComposerActionPort, ChatConversationActionPort, ChatExecutionActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

interface ChatComposerPrimaryActionHost {
    composer: ChatComposerActionPort;
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
}

type ComposerExecutionIntent = 'send' | 'stop' | 'queue' | 'steer' | 'resume' | 'blocked';

const HANDOFF_STOP_WAIT_MS = 10_000;
const HANDOFF_STOP_POLL_MS = 50;
const handoffStopConversationIds = new Set<string>();

const resolveComposerPrimaryIntent = (inputArguments: { admission: ChatTurnAdmissionSnapshot | null; isStreaming: boolean; actionMode: ChatComposerActionMode }): ComposerExecutionIntent => {
    if (inputArguments.actionMode === 'stop') {
        return inputArguments.admission?.canStop === true ? 'stop' : 'blocked';
    }
    if (inputArguments.actionMode === 'queue') {
        return inputArguments.admission?.canQueuePrompt === true ? 'queue' : 'send';
    }
    if (inputArguments.actionMode === 'resume') {
        return inputArguments.isStreaming ? 'blocked' : 'resume';
    }
    if (inputArguments.actionMode === 'steer' && inputArguments.admission?.canSteerPrompt === true) {
        return 'steer';
    }
    if (inputArguments.actionMode === 'steer') {
        return inputArguments.admission?.canQueuePrompt === true ? 'queue' : 'send';
    }
    if (!inputArguments.isStreaming) {
        return 'send';
    }
    if (inputArguments.admission?.canSteerPrompt === true) {
        return 'steer';
    }
    if (inputArguments.admission?.canQueuePrompt === true) {
        return 'queue';
    }
    return 'send';
};

const resolveSendMessageOperationId = (host: ChatComposerPrimaryActionHost): string => {
    const conversationId = normalizeConversationId(host.conversation.currentId());
    if (!conversationId) {
        return 'chat:sendMessage:new';
    }
    return `chat:sendMessage:${conversationId}`;
};

const createComposerPrimaryLoadingClear = (actionElement: HTMLElement | null | undefined): (() => void) | null => {
    return actionElement instanceof HTMLButtonElement ? beginLoadingButtonWithClear(actionElement) : null;
};

const sendMessageClearingOnCommit = async (host: ChatComposerPrimaryActionHost, clearLoading: (() => void) | null): Promise<void> => {
    await host.execution.send(clearLoading === null ? {} : { onEffectiveSendCommitted: clearLoading });
};

const stopStreamingForAdmission = (host: ChatComposerPrimaryActionHost, admission: ChatTurnAdmissionSnapshot): void => {
    const requestId = admission.activeStreamIdentity?.requestId;
    host.composer.noteUserStop(admission.conversationId, requestId ?? null);
    host.execution.stop({
        ...(requestId === undefined ? {} : { expectedRequestId: requestId }),
        forcePendingSteers: true
    });
};

const stopNextTurnAfterHandoff = async (host: ChatComposerPrimaryActionHost, conversationId: string): Promise<void> => {
    if (handoffStopConversationIds.has(conversationId)) return;
    handoffStopConversationIds.add(conversationId);
    const pollController = new AbortController();
    try {
        const deadline = monotonicMs() + HANDOFF_STOP_WAIT_MS;
        while (monotonicMs() < deadline) {
            if (normalizeConversationId(host.conversation.currentId()) !== conversationId || host.composer.resolvePrimaryActionMode() !== 'stop') return;
            const admission = host.execution.admission(conversationId);
            if (admission.canStop) {
                stopStreamingForAdmission(host, admission);
                return;
            }
            if (admission.phase === 'stopping') return;
            await sleepMsAbortable(pollController.signal, HANDOFF_STOP_POLL_MS);
        }
    } finally {
        pollController.abort();
        handoffStopConversationIds.delete(conversationId);
    }
};

const executeSyncedComposerPrimaryAction = async (host: ChatComposerPrimaryActionHost, conversationId: string, actionMode: ChatComposerActionMode, clearLoading: (() => void) | null): Promise<void> => {
    const admission = await host.execution.syncAdmission(conversationId);
    const isStreaming = admission.localUiActive || admission.backendActive;
    const intent = resolveComposerPrimaryIntent({
        admission,
        isStreaming,
        actionMode
    });
    if (isCurrentConversationExecuting(host) && !isStreaming && intent !== 'queue') {
        return;
    }
    if (intent === 'blocked') {
        return;
    }
    if (intent === 'stop') {
        stopStreamingForAdmission(host, admission);
        return;
    }
    if (intent === 'resume') {
        await host.composer.resumeConversationInputs(conversationId);
        return;
    }
    if (intent === 'queue') {
        const outcome = await host.execution.queue('queued');
        if (outcome === 'not-admitted') {
            await sendMessageClearingOnCommit(host, clearLoading);
        }
        return;
    }
    if (intent === 'steer') {
        await host.execution.steer();
        return;
    }
    await sendMessageClearingOnCommit(host, clearLoading);
};

const executeComposerPrimaryAction = (host: ChatComposerPrimaryActionHost, actionElement: HTMLElement | null = null, forceStop = false): void => {
    const conversationId = normalizeConversationId(host.conversation.currentId());
    const actionMode = forceStop ? 'stop' : host.composer.resolvePrimaryActionMode();
    const cachedAdmission = conversationId ? host.execution.admission(conversationId) : null;
    if (conversationId && actionMode === 'stop') {
        if (cachedAdmission?.canStop !== true) {
            if (host.composer.canStopHandoff()) {
                host.execution.run(`chat:stopStreaming:${conversationId}:handoff`, () => stopNextTurnAfterHandoff(host, conversationId));
            }
            return;
        }
        const requestId = cachedAdmission.activeStreamIdentity?.requestId ?? 'pending';
        host.execution.run(`chat:stopStreaming:${conversationId}:${requestId}`, () => {
            stopStreamingForAdmission(host, cachedAdmission);
        });
        collapseSidebarIfNarrowViewport(host);
        return;
    }
    const clearLoading = createComposerPrimaryLoadingClear(actionElement);
    if (!conversationId) {
        runCollapsedUiTask(host, resolveSendMessageOperationId(host), async () => {
            try {
                await sendMessageClearingOnCommit(host, clearLoading);
            } finally {
                clearLoading?.();
            }
        });
        return;
    }
    const operationId = actionMode === 'stop' ? 'chat:stopStreaming' : actionMode === 'queue' ? 'chat:queueConversationInput' : actionMode === 'steer' ? 'chat:steerActiveStream' : actionMode === 'resume' ? 'chat:resumeConversationInputs' : resolveSendMessageOperationId(host);
    runCollapsedUiTask(host, operationId, async () => {
        try {
            await executeSyncedComposerPrimaryAction(host, conversationId, actionMode, clearLoading);
        } finally {
            clearLoading?.();
        }
    });
};

export { executeComposerPrimaryAction };
