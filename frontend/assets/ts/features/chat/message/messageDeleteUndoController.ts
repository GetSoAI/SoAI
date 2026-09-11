/* SoAI - Chat feature message delete undo controller [frontend/assets/ts/features/chat/message/messageDeleteUndoController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { ConversationExecutionRunResult } from '@core/chat/protocols.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { ChatMessageDeleteUndoCommitQueue } from '@features/chat/message/messageDeleteUndoCommitQueue.ts';
import { ChatMessageDeleteUndoConversationResolver } from '@features/chat/message/messageDeleteUndoConversationResolver.ts';
import { ChatMessageDeleteUndoPendingRegistry, type PendingDeleteDescriptor } from '@features/chat/message/messageDeleteUndoPendingRegistry.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import { buildPersistedMessageCursorKey, resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import type { ResolvedMessageReference } from '@features/chat/message/messageReferenceResolution.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface ChatMessageDeleteUndoControllerDependencies {
    getCurrentConversation: () => ConversationContract | null;
    resolveConversationById: (conversationId: string) => ConversationContract | null;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    resolveMessageReference: (conversation: ConversationContract, messageDomId: string) => ResolvedMessageReference;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    renderCurrentConversation: () => Promise<void>;
    renderConversationList: () => Promise<void>;
    saveAndSync: (conversation: ConversationContract) => Promise<void>;
    deleteMessageByCursor: (conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number }) => Promise<void>;
    runConversationExecutionIfIdle: (conversationId: string, task: () => Promise<void>) => Promise<ConversationExecutionRunResult>;
    showNotification: (message: string, type: NotificationType) => void;
    notifyConversationContentCommitted: () => void;
    getDeleteFailedText: () => string;
}

class ChatMessageDeleteUndoController {
    readonly #dependencies: ChatMessageDeleteUndoControllerDependencies;
    readonly #conversationResolver: ChatMessageDeleteUndoConversationResolver;
    readonly #pendingRegistry: ChatMessageDeleteUndoPendingRegistry;
    readonly #commitQueue: ChatMessageDeleteUndoCommitQueue;
    readonly #resources = new ResourceTracker();
    #isDisposed: boolean;

    constructor(dependencies: ChatMessageDeleteUndoControllerDependencies, options?: { deleteDelayMs?: number }) {
        this.#dependencies = dependencies;
        this.#conversationResolver = new ChatMessageDeleteUndoConversationResolver({
            getCurrentConversation: () => this.#dependencies.getCurrentConversation(),
            resolveConversationById: (conversationId) => this.#dependencies.resolveConversationById(conversationId)
        });
        this.#commitQueue = new ChatMessageDeleteUndoCommitQueue();
        this.#isDisposed = false;
        const delayMsRaw = options?.deleteDelayMs;
        const delayMs = typeof delayMsRaw === 'number' && Number.isFinite(delayMsRaw) && delayMsRaw > 0 ? Math.floor(delayMsRaw) : 5000;
        this.#pendingRegistry = new ChatMessageDeleteUndoPendingRegistry({
            deleteDelayMs: delayMs,
            onCommitTimer: (conversationKey, targetKey, nonce) => this.#handleCommitTimer(conversationKey, targetKey, nonce),
            timers: {
                setTimeout: (callback, delay) => this.#resources.setTimeout(callback, delay),
                clearTimer: (timerId) => this.#resources.clearTimer(timerId)
            }
        });
    }

    dispose(): void {
        if (this.#isDisposed) {
            return;
        }
        this.#isDisposed = true;
        this.#pendingRegistry.dispose();
        this.#commitQueue.dispose();
        this.#conversationResolver.dispose();
        this.#resources.cleanup();
    }

    async #rerenderCurrentConversationIfMatching(conversationKey: string): Promise<boolean> {
        if (!this.#conversationResolver.isCurrentConversationKey(conversationKey)) {
            return false;
        }
        await this.#dependencies.renderCurrentConversation();
        return true;
    }

    isPendingForConversation(conversation: ConversationContract | null, messageDomId: string): boolean {
        if (this.#isDisposed) {
            return false;
        }
        if (!conversation) {
            return false;
        }
        const normalizedMessageDomId = normalizeMessageDomId(messageDomId);
        if (!normalizedMessageDomId) {
            return false;
        }
        const key = this.#conversationResolver.resolveKey(conversation);
        return this.#pendingRegistry.isPending(key, normalizedMessageDomId);
    }

    pauseDeleteCountdown(conversation: ConversationContract, messageDomId: string): void {
        if (this.#isDisposed) {
            return;
        }
        const normalizedMessageDomId = normalizeMessageDomId(messageDomId);
        if (!normalizedMessageDomId) {
            return;
        }
        const conversationKey = this.#conversationResolver.resolveKey(conversation);
        this.#pendingRegistry.pauseDeleteCountdown(conversationKey, normalizedMessageDomId);
    }

    resumeDeleteCountdown(conversation: ConversationContract, messageDomId: string): void {
        if (this.#isDisposed) {
            return;
        }
        const normalizedMessageDomId = normalizeMessageDomId(messageDomId);
        if (!normalizedMessageDomId) {
            return;
        }
        const conversationKey = this.#conversationResolver.resolveKey(conversation);
        this.#pendingRegistry.resumeDeleteCountdown(conversationKey, normalizedMessageDomId);
    }

    async requestDelete(conversation: ConversationContract, messageDomId: string): Promise<void> {
        if (this.#isDisposed) {
            return;
        }
        const normalizedMessageDomId = normalizeMessageDomId(messageDomId);
        if (!normalizedMessageDomId) {
            return;
        }
        const conversationKey = this.#conversationResolver.resolveKey(conversation);
        const reference = this.#dependencies.resolveMessageReference(conversation, normalizedMessageDomId);
        const cursor = reference.message === null ? null : resolvePersistedMessageCursor(reference.message);
        if (reference.message === null || (cursor === null && conversation.history !== undefined)) {
            throw new Error('Persisted deleted message cursor is missing.');
        }
        const created = this.#pendingRegistry.requestDelete(conversationKey, normalizedMessageDomId, cursor);
        if (!created) {
            return;
        }
        this.#dependencies.invalidateChatMarkup('current');
        await this.#dependencies.renderCurrentConversation();
    }

    async undoDelete(conversation: ConversationContract, messageDomId: string): Promise<void> {
        if (this.#isDisposed) {
            return;
        }
        const normalizedMessageDomId = normalizeMessageDomId(messageDomId);
        if (!normalizedMessageDomId) {
            return;
        }
        const conversationKey = this.#conversationResolver.resolveKey(conversation);
        const wasPending = this.#pendingRegistry.undoDelete(conversationKey, normalizedMessageDomId);
        if (!wasPending) {
            return;
        }
        if (!this.#pendingRegistry.isConversationActive(conversationKey)) {
            this.#conversationResolver.releaseLocalConversationKey(conversationKey);
        }
        this.#dependencies.invalidateChatMarkup('current');
        await this.#dependencies.renderCurrentConversation();
    }

    async commitDeleteNow(conversation: ConversationContract, messageDomId: string): Promise<void> {
        if (this.#isDisposed) {
            return;
        }
        const normalizedMessageDomId = normalizeMessageDomId(messageDomId);
        if (!normalizedMessageDomId) {
            return;
        }
        const conversationKey = this.#conversationResolver.resolveKey(conversation);
        await this.#enqueueCommit(conversationKey, () => this.#pendingRegistry.commitNowByRenderIdentity(conversationKey, normalizedMessageDomId), { requireExecutionLease: true });
    }

    async commitAllPendingDeletes(conversation: ConversationContract): Promise<void> {
        if (this.#isDisposed) {
            return;
        }
        const conversationKey = this.#conversationResolver.resolveKey(conversation);
        const pendingTargetKeys = this.#pendingRegistry.listPendingTargetKeys(conversationKey);
        for (const targetKey of pendingTargetKeys) {
            await this.#enqueueCommit(conversationKey, () => this.#pendingRegistry.commitNow(conversationKey, targetKey));
        }
        await this.#commitQueue.waitForIdle(conversationKey);
    }

    resumePausedDeletesForConversation(conversation: ConversationContract): void {
        if (this.#isDisposed) return;
        this.#pendingRegistry.resumeAllPaused(this.#conversationResolver.resolveKey(conversation));
    }

    #handleCommitTimer(conversationKey: string, targetKey: string, nonce: string): void {
        if (this.#isDisposed) {
            return;
        }
        terminateHandledPromise(this.#enqueueCommit(conversationKey, () => this.#pendingRegistry.commitIfCurrent(conversationKey, targetKey, nonce), { throwOnFailure: false, requireExecutionLease: true, onBusy: () => this.#pendingRegistry.deferIfCurrent(conversationKey, targetKey, nonce) }));
    }

    async #enqueueCommit(conversationKey: string, commit: () => { descriptor: PendingDeleteDescriptor | null }, options?: { throwOnFailure?: boolean; requireExecutionLease?: boolean; onBusy?: () => void }): Promise<void> {
        const throwOnFailure = options?.throwOnFailure ?? true;
        await this.#commitQueue.enqueue(
            conversationKey,
            async () => {
                const executeCommit = async (): Promise<void> =>
                    await this.#dependencies.runWithBoundary('chat:deleteMessageCommit', async () => {
                        if (this.#isDisposed) {
                            return;
                        }
                        const commitResult = commit();
                        const descriptor = commitResult.descriptor;
                        if (descriptor === null) {
                            return;
                        }

                        const conversation = this.#conversationResolver.resolveConversationByKey(conversationKey);
                        if (!conversation) {
                            this.#pendingRegistry.settle(conversationKey, descriptor.targetKey);
                            await this.#rerenderCurrentConversationIfMatching(conversationKey);
                            return;
                        }

                        let rerenderedCurrentConversation = false;
                        let removedLocalMessage: { index: number; message: ChatMessage } | null = null;
                        try {
                            if (descriptor.cursor !== null && conversation.id) {
                                await this.#dependencies.deleteMessageByCursor(conversation, {
                                    createdAtMs: descriptor.cursor.createdAtMs,
                                    messageId: descriptor.cursor.id
                                });
                            } else if (descriptor.cursor === null) {
                                const reference = this.#dependencies.resolveMessageReference(conversation, descriptor.renderIdentity);
                                if (reference.message === null || reference.index < 0) {
                                    this.#pendingRegistry.settle(conversationKey, descriptor.targetKey);
                                    await this.#rerenderCurrentConversationIfMatching(conversationKey);
                                    return;
                                }
                                removedLocalMessage = { index: reference.index, message: reference.message };
                                conversation.messages.splice(reference.index, 1);
                                if (conversation.id) await this.#dependencies.saveAndSync(conversation);
                            }
                        } catch (error) {
                            const runtimeError = ensureError(error);
                            if (removedLocalMessage !== null) {
                                const insertIndex = clampNumber(removedLocalMessage.index, 0, conversation.messages.length);
                                conversation.messages.splice(insertIndex, 0, removedLocalMessage.message);
                            }
                            this.#pendingRegistry.settle(conversationKey, descriptor.targetKey);
                            try {
                                await this.#rerenderCurrentConversationIfMatching(conversationKey);
                            } catch (recoveryError) {
                                errorHandler.error('ChatMessageDeleteUndoController', 'Delete rollback conversation render failed', ensureError(recoveryError));
                            }
                            try {
                                this.#dependencies.invalidateChatMarkup('list');
                                await this.#dependencies.renderConversationList();
                            } catch (recoveryError) {
                                errorHandler.error('ChatMessageDeleteUndoController', 'Delete rollback conversation list refresh failed', ensureError(recoveryError));
                            }
                            try {
                                this.#dependencies.showNotification(this.#dependencies.getDeleteFailedText(), 'error');
                            } catch (notificationError) {
                                errorHandler.error('ChatMessageDeleteUndoController', 'Delete failure notification failed', ensureError(notificationError));
                            }
                            if (throwOnFailure) {
                                throw runtimeError;
                            }
                            return;
                        }
                        this.#pendingRegistry.settle(conversationKey, descriptor.targetKey);
                        if (descriptor.cursor !== null) {
                            const deletedCursorKey = buildPersistedMessageCursorKey(descriptor.cursor);
                            conversation.messages = conversation.messages.filter((message) => {
                                const messageCursor = resolvePersistedMessageCursor(message);
                                return messageCursor === null || buildPersistedMessageCursorKey(messageCursor) !== deletedCursorKey;
                            });
                        }
                        rerenderedCurrentConversation = await this.#rerenderCurrentConversationIfMatching(conversationKey);
                        this.#dependencies.invalidateChatMarkup('list');
                        await this.#dependencies.renderConversationList();
                        if (conversation.id && rerenderedCurrentConversation) {
                            try {
                                this.#dependencies.notifyConversationContentCommitted();
                            } catch (error) {
                                errorHandler.error('ChatMessageDeleteUndoController', 'Post-commit conversation notification failed', ensureError(error));
                            }
                        }
                    });
                const conversation = this.#conversationResolver.resolveConversationByKey(conversationKey);
                const conversationId = typeof conversation?.id === 'string' ? conversation.id.trim() : '';
                if (options?.requireExecutionLease === true && conversationId) {
                    const executionResult = await this.#dependencies.runConversationExecutionIfIdle(conversationId, executeCommit);
                    if (executionResult.status === 'busy') {
                        options.onBusy?.();
                    }
                    return;
                }
                await executeCommit();
            },
            {
                isKeyActive: (key: string): boolean => this.#pendingRegistry.isConversationActive(key),
                onKeyIdle: (key: string): void => this.#conversationResolver.releaseLocalConversationKey(key)
            }
        );
    }
}

export { ChatMessageDeleteUndoController };
