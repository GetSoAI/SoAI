/* SoAI - Composer send flow control [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/sendMessageFlowController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatContentSegment } from '@features/chat/public.ts';
import type { ConversationExecutionRunResult } from '@core/chat/protocols.ts';
import { isAbortError, runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ConversationSendLockManager, resolveSendLockKey } from '@pages/chat/controllers/chatmessagesendingcontroller/ConversationSendLockManager.ts';
import { QUEUED_SEND_ABORTED, QUEUED_SEND_SENT } from '@pages/chat/controllers/chatmessagesendingcontroller/constants.ts';
import { resolveComposerPayloadForSubmission, type ComposerPayload } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import { sendMessageWithResolvedPayload, type ConversationInputIntent, type PostAdmissionHook, type QueuedSendGuard } from '@pages/chat/controllers/chatmessagesendingcontroller/service.ts';
import type { ConversationInputComposerOutcome, MessageSendingHost, QueuedSendOutcome, SendMessageOptions } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const runWithConversationSendLockIfIdle = async (inputArguments: { manager: ConversationSendLockManager; conversationId: string | null | undefined; task: () => Promise<void>; canReleaseBusyLock?: () => boolean }): Promise<ConversationExecutionRunResult> => {
    const lockKey = resolveSendLockKey(inputArguments.conversationId);
    let lease = inputArguments.manager.tryAcquire([lockKey]);
    if (lease === null) {
        if (inputArguments.canReleaseBusyLock?.() === true) {
            inputArguments.manager.releaseKeys([lockKey]);
            lease = inputArguments.manager.tryAcquire([lockKey]);
        }
        if (lease === null) {
            return { status: 'busy' };
        }
    }
    try {
        await inputArguments.task();
        return { status: 'completed' };
    } finally {
        lease.release();
    }
};

const sendMessageFromComposer = async (inputArguments: { host: MessageSendingHost; manager: ConversationSendLockManager; afterAdmission?: PostAdmissionHook | null } & SendMessageOptions): Promise<void> => {
    const host = inputArguments.host;
    const afterAdmission = inputArguments.afterAdmission ?? null;
    const initialSendLockKey = resolveSendLockKey(host.conversation.getCurrentConversation()?.id);
    const lease = inputArguments.manager.tryAcquire([initialSendLockKey]);
    if (lease === null) {
        return;
    }

    try {
        const payload = await resolveComposerPayloadForSubmission(host);
        if (!payload) {
            return;
        }
        await sendMessageWithResolvedPayload({ host, lockLease: lease, initialSendLockKey, payload, applyComposerSideEffects: true, onEffectiveSendCommitted: inputArguments.onEffectiveSendCommitted, afterAdmission });
    } finally {
        lease.release();
    }
};

const sendMessageFromPayload = async (inputArguments: { host: MessageSendingHost; manager: ConversationSendLockManager; payload: ComposerPayload; afterAdmission?: PostAdmissionHook | null }): Promise<void> => {
    const host = inputArguments.host;
    const afterAdmission = inputArguments.afterAdmission ?? null;
    const initialSendLockKey = resolveSendLockKey(host.conversation.getCurrentConversation()?.id);
    const lease = inputArguments.manager.tryAcquire([initialSendLockKey]);
    if (lease === null) {
        return;
    }

    try {
        await sendMessageWithResolvedPayload({ host, lockLease: lease, initialSendLockKey, payload: inputArguments.payload, applyComposerSideEffects: false, afterAdmission });
    } finally {
        lease.release();
    }
};

const sendQueuedTextMessage = async (inputArguments: { host: MessageSendingHost; manager: ConversationSendLockManager; text: string; attachmentContent: readonly ChatContentSegment[]; signal: AbortSignal; beforeSend: QueuedSendGuard; afterAdmission?: PostAdmissionHook | null }): Promise<QueuedSendOutcome> => {
    const host = inputArguments.host;
    const afterAdmission = inputArguments.afterAdmission ?? null;
    const messageText = typeof inputArguments.text === 'string' ? inputArguments.text.trim() : '';
    if (!messageText && inputArguments.attachmentContent.length === 0) {
        return QUEUED_SEND_SENT;
    }
    const initialSendLockKey = resolveSendLockKey(host.conversation.getCurrentConversation()?.id);
    const lease = await inputArguments.manager.acquire([initialSendLockKey], inputArguments.signal);
    try {
        if (inputArguments.signal.aborted) {
            return QUEUED_SEND_ABORTED;
        }
        return await sendMessageWithResolvedPayload({
            host,
            lockLease: lease,
            initialSendLockKey,
            payload: {
                messageText,
                sourceText: messageText,
                attachmentContent: [...inputArguments.attachmentContent],
                attachments: [],
                draftRevision: null
            },
            applyComposerSideEffects: false,
            beforeSend: inputArguments.beforeSend,
            afterAdmission,
            abortSignal: inputArguments.signal
        });
    } finally {
        lease.release();
    }
};

const sendConversationInputFromComposer = async (inputArguments: { host: MessageSendingHost; manager: ConversationSendLockManager; intent: ConversationInputIntent; afterAdmission?: PostAdmissionHook | null }): Promise<ConversationInputComposerOutcome> => {
    const host = inputArguments.host;
    const initialSendLockKey = resolveSendLockKey(host.conversation.getCurrentConversation()?.id);
    try {
        return await runWithAbortSignalScope([host.platform.getRuntimeAbortSignal()], async (signal) => {
            const lease = await inputArguments.manager.acquire([initialSendLockKey], signal);
            try {
                const payload = await resolveComposerPayloadForSubmission(host);
                if (!payload) return 'empty';
                const outcome = await sendMessageWithResolvedPayload({
                    host,
                    lockLease: lease,
                    initialSendLockKey,
                    payload,
                    applyComposerSideEffects: true,
                    inputIntent: inputArguments.intent,
                    afterAdmission: inputArguments.afterAdmission ?? null,
                    abortSignal: signal
                });
                if (outcome.status === 'sent') return 'enqueued';
                if (outcome.status === 'aborted') return 'stale';
                if (outcome.reason === 'conversation-mismatch') return 'conversation-changed';
                if (outcome.reason === 'streaming') return 'not-admitted';
                return 'stale';
            } finally {
                lease.release();
            }
        });
    } catch (error) {
        if (isAbortError(error)) return 'stale';
        throw error;
    }
};

export { runWithConversationSendLockIfIdle, sendConversationInputFromComposer, sendMessageFromComposer, sendMessageFromPayload, sendQueuedTextMessage };
