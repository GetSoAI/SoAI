/* SoAI - Canonical durable Chat input admission [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { ChatExecutionModelPreflightBlockedError, applyChatExecutionModelStateToConversation, captureConversationMutationSnapshot, captureSoaiLinkWorkspaceSnapshot, isChatConversationSettingsWritable, matchesSoaiLinkWorkspaceSnapshot, mountOptimisticInputUserMessage, resolveOptimisticInputOrderingAnchor, restoreConversationMutationSnapshot, showChatExecutionModelPreflightBlockedError } from '@features/chat/public.ts';
import { capturePayloadAttachmentSnapshot, matchesPayloadAttachmentSnapshot } from '@pages/chat/controllers/chatmessagesendingcontroller/chatAttachmentPayloadRevisionController.ts';
import { getChatSyncErrorTitle, refreshComposerState, refreshConversationListAfterSharedSync, requireCurrentConversationForSend, type ComposerPayload } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import { applyLockedUserInstructionForSend } from '@pages/chat/controllers/chatmessagesendingcontroller/userInstructionLockSendController.ts';
import { commitEffectiveSendVisualState } from '@pages/chat/controllers/chatmessagesendingcontroller/effectiveSendVisualCommitController.ts';
import { resolveSelectedModelPreflight, resolveSendExecutionModelPreflight } from '@pages/chat/controllers/chatmessagesendingcontroller/executionModelPreflightController.ts';
import { resolveSendLockKey, type SendLockLease } from '@pages/chat/controllers/chatmessagesendingcontroller/ConversationSendLockManager.ts';
import { claimDraftKnowledgeAttachments } from '@pages/chat/controllers/chatmessagesendingcontroller/knowledgeAttachmentClaimController.ts';
import { resolveComposerSoaiLinks, resolvePayloadSoaiLinks } from '@pages/chat/controllers/chatmessagesendingcontroller/soaiLinkPayloadController.ts';
import { QUEUED_SEND_ABORTED, QUEUED_SEND_SENT, blockQueuedSend } from '@pages/chat/controllers/chatmessagesendingcontroller/constants.ts';
import { runQueuedSendGuard } from '@pages/chat/controllers/chatmessagesendingcontroller/sendFlowGuardController.ts';
import { blockSendForConversationMismatch, isWorkspaceScopeChangedError, recoverFailedSendSurface } from '@pages/chat/controllers/chatmessagesendingcontroller/sendFlowRecoveryController.ts';
import type { MessageSendingHost, QueuedSendGuard, QueuedSendOutcome, SendMessageOptions } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

type PostAdmissionHook = (conversationId: string) => void;
type ConversationInputIntent = 'prompt' | 'steer';

const runPostAdmissionHook = (host: MessageSendingHost, conversationId: string, hook: PostAdmissionHook | null | undefined): void => {
    try {
        hook?.(conversationId);
    } catch (error) {
        host.platform.handleError(ensureError(error), getChatSyncErrorTitle(), { notify: true });
    }
};

const canAdmitSteer = async (host: MessageSendingHost, conversationId: string, signal?: AbortSignal | null): Promise<boolean> => {
    const admission = await host.services.getChatStreamingController().resolveSyncedTurnAdmission(conversationId, signal ?? null);
    return admission.canSteerPrompt;
};

const sendMessageWithResolvedPayload = async (inputArguments: { host: MessageSendingHost; lockLease: SendLockLease; initialSendLockKey: string; payload: ComposerPayload; applyComposerSideEffects: boolean; inputIntent?: ConversationInputIntent; beforeSend?: QueuedSendGuard | null; afterAdmission?: PostAdmissionHook | null; abortSignal?: AbortSignal | null } & SendMessageOptions): Promise<QueuedSendOutcome> => {
    const host = inputArguments.host;
    const inputIntent = inputArguments.inputIntent ?? 'prompt';
    let payload = inputArguments.payload;
    const composerTextForClearing = payload.messageText;
    const attachmentManager = host.services.getAttachmentManager();
    if (inputArguments.lockLease.keys[0] !== inputArguments.initialSendLockKey) return blockQueuedSend('stale');
    throwIfAborted(inputArguments.abortSignal, 'Queued chat send was aborted.');
    const currentConversation = host.conversation.getCurrentConversation();
    const selectedModelId = host.model.getCurrentModel();
    if (selectedModelId !== null || currentConversation === null) {
        const selectedModelPreflight = resolveSelectedModelPreflight(host, selectedModelId);
        if (selectedModelPreflight !== null) return selectedModelPreflight;
    }
    const currentConversationResolution = await requireCurrentConversationForSend(host);
    const conversation = currentConversationResolution.conversation;
    const conversationId = conversation.id;
    if (!inputArguments.lockLease.addKey(resolveSendLockKey(conversationId))) return blockQueuedSend('stale');
    if (inputIntent === 'steer' && !(await canAdmitSteer(host, conversationId, inputArguments.abortSignal ?? null))) return blockQueuedSend('streaming');
    const workspaceSnapshot = captureSoaiLinkWorkspaceSnapshot(conversation);
    const isFirstMessage = (conversation.history?.totalCount ?? conversation.messageCount ?? conversation.messages.length) === 0;
    const runSendGuard = (): QueuedSendOutcome =>
        runQueuedSendGuard({
            beforeSend: inputArguments.beforeSend,
            conversationId,
            initialSendLockKey: inputArguments.initialSendLockKey,
            createdConversationForSend: currentConversationResolution.createdForSend,
            isFirstMessage,
            chatStreamingController: host.services.getChatStreamingController()
        });
    let guardOutcome = runSendGuard();
    if (guardOutcome.status !== 'sent') return guardOutcome;
    await host.conversation.waitForPendingAgentModeUpdate();
    const executionModelPreflight = resolveSendExecutionModelPreflight(host, conversation);
    if (executionModelPreflight.status === 'blocked') return executionModelPreflight.outcome;
    const modelPreflight = executionModelPreflight.plan;
    const executionAgentMode = host.conversation.resolveAgentModeForConversation(conversationId);
    const isWorkspaceCurrent = (): boolean => matchesSoaiLinkWorkspaceSnapshot(host.conversation.getCurrentConversation(), workspaceSnapshot);
    await host.conversation.commitPendingDeletesForConversation(conversation);
    if (!host.conversation.getConversationById(conversationId)) return blockQueuedSend('conversation-mismatch');
    const mutationSnapshot = captureConversationMutationSnapshot(conversation);
    let didPersistConversation = false;
    let didPrepareComposerSurface = false;
    let didClearComposerInput = false;
    try {
        if (isChatConversationSettingsWritable(conversation)) {
            applyChatExecutionModelStateToConversation(conversation, {
                primaryModelId: modelPreflight.primaryModelId,
                agentMode: executionAgentMode
            });
            await applyLockedUserInstructionForSend(host, conversation, conversationId);
        }
        guardOutcome = runSendGuard();
        if (guardOutcome.status !== 'sent') {
            restoreConversationMutationSnapshot(conversation, mutationSnapshot);
            return guardOutcome;
        }
        const resolvedSoaiLinkPayload = inputArguments.applyComposerSideEffects ? await resolveComposerSoaiLinks(host, conversationId, payload) : await resolvePayloadSoaiLinks(host, conversationId, payload, inputArguments.abortSignal ?? null);
        if (resolvedSoaiLinkPayload === null || host.conversation.getCurrentConversation()?.id !== conversationId || !isWorkspaceCurrent()) {
            return blockSendForConversationMismatch({ host, conversation, mutationSnapshot, restoreConversation: true, workspaceCurrent: isWorkspaceCurrent() });
        }
        payload = resolvedSoaiLinkPayload;
        const attachmentSnapshot = capturePayloadAttachmentSnapshot({
            attachments: payload.attachments,
            attachmentContent: attachmentManager.buildContentFragmentsFromAttachments(payload.attachments)
        });
        const knowledgeClaimPayload = await claimDraftKnowledgeAttachments(host, conversationId, payload, inputArguments.abortSignal ?? null);
        if (knowledgeClaimPayload === null) {
            restoreConversationMutationSnapshot(conversation, mutationSnapshot);
            refreshComposerState(host);
            return blockQueuedSend('stale');
        }
        payload = knowledgeClaimPayload;
        if (host.conversation.getCurrentConversation()?.id !== conversationId || !isWorkspaceCurrent()) {
            return blockSendForConversationMismatch({ host, conversation, mutationSnapshot, restoreConversation: true, workspaceCurrent: isWorkspaceCurrent() });
        }
        const draftRevision = attachmentManager.getDraftRevision();
        const currentAttachments = attachmentManager.getAttachments();
        const currentAttachmentContent = attachmentManager.buildContentFragmentsFromAttachments(currentAttachments);
        if (payload.draftRevision !== null && draftRevision !== payload.draftRevision && attachmentSnapshot !== null && matchesPayloadAttachmentSnapshot({ currentAttachments, currentAttachmentContent, capturedSnapshot: attachmentSnapshot })) payload = { ...payload, draftRevision };
        if (payload.draftRevision !== null && attachmentManager.getDraftRevision() !== payload.draftRevision) {
            restoreConversationMutationSnapshot(conversation, mutationSnapshot);
            refreshComposerState(host);
            return blockQueuedSend('stale');
        }
        throwIfAborted(inputArguments.abortSignal, 'Queued chat send was aborted.');
        guardOutcome = runSendGuard();
        if (guardOutcome.status !== 'sent') {
            restoreConversationMutationSnapshot(conversation, mutationSnapshot);
            return guardOutcome;
        }
        const conversationManager = host.services.getConversationManager();
        await conversationManager.ensureConversationPersisted(conversation);
        if (isChatConversationSettingsWritable(conversation)) {
            await conversationManager.updateConversationSettings(conversationId, {
                model: modelPreflight.primaryModelId,
                agent: { mode: executionAgentMode }
            });
        }
        didPersistConversation = true;
        attachmentManager.markDraftCommitStarted();
        const optimisticInputOrderingAnchor = resolveOptimisticInputOrderingAnchor(conversation);
        const enqueuedInput = await host.services.getConversationInputsManager().enqueue(conversationId, {
            intent: inputIntent === 'steer' ? 'steer' : 'queued',
            text: payload.messageText || null,
            sourceText: payload.sourceText || null,
            attachmentContent: payload.attachmentContent
        });
        if (enqueuedInput.isDispatchableHead) {
            mountOptimisticInputUserMessage({
                conversation,
                inputId: enqueuedInput.inputId,
                acceptedAtMs: enqueuedInput.acceptedAtMs,
                orderingAnchorTimestamp: optimisticInputOrderingAnchor,
                text: payload.messageText || null,
                attachmentContent: payload.attachmentContent
            });
        }
        try {
            const isCurrent = host.conversation.getCurrentConversation()?.id === conversationId;
            if (isCurrent) {
                const hasAttachmentSurface = payload.attachments.length > 0 || payload.attachmentContent.length > 0;
                await commitEffectiveSendVisualState(host, {
                    composerTextForClearing: inputArguments.applyComposerSideEffects ? composerTextForClearing : null,
                    abortSignal: null,
                    renderCurrentConversation: () => host.presentation.renderCurrentConversation(),
                    prepareComposerSurfaceForEffectiveSend: inputArguments.applyComposerSideEffects && hasAttachmentSurface ? (): void => host.presentation.hideAttachedFilesPreview() : undefined,
                    onComposerSurfacePrepared: () => {
                        didPrepareComposerSurface = true;
                    },
                    onComposerCleared: () => {
                        didClearComposerInput = true;
                    }
                });
                inputArguments.onEffectiveSendCommitted?.();
            }
            if (inputArguments.applyComposerSideEffects) attachmentManager.checkoutAttachments(payload.attachments);
            runPostAdmissionHook(host, conversationId, inputArguments.afterAdmission);
            await refreshConversationListAfterSharedSync(host);
            refreshComposerState(host);
        } catch (error) {
            host.platform.handleError(ensureError(error), getChatSyncErrorTitle(), { notify: true });
        }
        return QUEUED_SEND_SENT;
    } catch (error) {
        const coercedError = ensureError(error);
        if (isAbortError(coercedError)) {
            await recoverFailedSendSurface({ host, conversation, conversationId, mutationSnapshot, restoreConversation: !didPersistConversation, composerTextForClearing, didPrepareComposerSurface, didClearComposerInput, didPersistConversation });
            return QUEUED_SEND_ABORTED;
        }
        if (coercedError instanceof ChatExecutionModelPreflightBlockedError) {
            showChatExecutionModelPreflightBlockedError(coercedError.reason);
            await recoverFailedSendSurface({ host, conversation, conversationId, mutationSnapshot, restoreConversation: !didPersistConversation, composerTextForClearing, didPrepareComposerSurface, didClearComposerInput, didPersistConversation });
            return blockQueuedSend('stale');
        }
        if (isWorkspaceScopeChangedError(coercedError)) return blockSendForConversationMismatch({ host, conversation, mutationSnapshot, restoreConversation: !didPersistConversation, workspaceCurrent: false });
        await recoverFailedSendSurface({ host, conversation, conversationId, mutationSnapshot, restoreConversation: !didPersistConversation, composerTextForClearing, didPrepareComposerSurface, didClearComposerInput, didPersistConversation });
        throw coercedError;
    }
};

export { sendMessageWithResolvedPayload };
export type { ConversationInputIntent, PostAdmissionHook, QueuedSendGuard };
