/* SoAI - Chat page composer primary action controller [frontend/assets/ts/pages/chat/controllers/actionhandlers/core/composerPrimaryActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { normalizeConversationId, type ChatComposerActionMode, type ChatTurnAdmissionSnapshot } from '@features/chat/public.ts';
import { isCurrentConversationExecuting, runCollapsedUiTask } from '@pages/chat/controllers/actionhandlers/core/effects.ts';
import type { ChatComposerActionPort, ChatConversationActionPort, ChatExecutionActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

interface ChatComposerPrimaryActionHost {
    composer: ChatComposerActionPort;
    conversation: ChatConversationActionPort;
    execution: ChatExecutionActionPort;
}

type ComposerExecutionIntent = 'send' | 'stop' | 'queue' | 'steer';

const resolveComposerPrimaryIntent = (inputArguments: { admission: ChatTurnAdmissionSnapshot | null; isStreaming: boolean; actionMode: ChatComposerActionMode }): ComposerExecutionIntent => {
    if (inputArguments.actionMode === 'stop' && inputArguments.admission?.canStop === true) {
        return 'stop';
    }
    if (inputArguments.actionMode === 'queue') {
        return inputArguments.admission?.canQueuePrompt === true ? 'queue' : 'send';
    }
    if (inputArguments.actionMode === 'stop') {
        return 'send';
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

const stopStreamingForAdmission = async (host: ChatComposerPrimaryActionHost, conversationId: string, admission: ChatTurnAdmissionSnapshot): Promise<void> => {
    const requestId = admission.activeStreamIdentity?.requestId;
    host.execution.stop({
        ...(requestId === undefined ? {} : { expectedRequestId: requestId }),
        forcePendingSteers: true
    });
    if (requestId !== undefined) {
        await host.execution.waitForRequestExit(conversationId, requestId);
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
    if (intent === 'stop') {
        await stopStreamingForAdmission(host, conversationId, admission);
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
        const outcome = await host.execution.steer();
        if (outcome === 'not-admitted') {
            await sendMessageClearingOnCommit(host, clearLoading);
        }
        return;
    }
    await sendMessageClearingOnCommit(host, clearLoading);
};

const executeComposerPrimaryAction = (host: ChatComposerPrimaryActionHost, actionElement: HTMLElement | null = null): void => {
    const conversationId = normalizeConversationId(host.conversation.currentId());
    const actionMode = host.composer.resolvePrimaryActionMode();
    const cachedAdmission = conversationId ? host.execution.admission(conversationId) : null;
    const clearLoading = createComposerPrimaryLoadingClear(actionElement);
    if (conversationId && actionMode === 'stop' && cachedAdmission?.canStop === true) {
        runCollapsedUiTask(host, 'chat:stopStreaming', async () => {
            try {
                await stopStreamingForAdmission(host, conversationId, cachedAdmission);
            } finally {
                clearLoading?.();
            }
        });
        return;
    }
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
    const operationId = actionMode === 'stop' ? 'chat:stopStreaming' : actionMode === 'queue' ? 'chat:queueConversationInput' : actionMode === 'steer' ? 'chat:steerActiveStream' : resolveSendMessageOperationId(host);
    runCollapsedUiTask(host, operationId, async () => {
        try {
            await executeSyncedComposerPrimaryAction(host, conversationId, actionMode, clearLoading);
        } finally {
            clearLoading?.();
        }
    });
};

export { executeComposerPrimaryAction };
