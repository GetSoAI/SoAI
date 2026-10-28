/* SoAI - Canonical durable Chat input admission [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
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
import type { AcceptedConversationInput, Conversation, MessageSendingHost, QueuedSendGuard, QueuedSendOutcome, SendMessageOptions } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

import type { ConversationActivationSnapshot } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';

type PostAdmissionHook = (conversationId: string) => void;
type ConversationInputIntent = 'prompt' | 'steer';

const runPostAdmissionHook = (host: MessageSendingHost, conversationId: string, hook: PostAdmissionHook | null | undefined): void => {
    try {
        hook?.(conversationId);
    } catch (error) {
        host.platform.handleError(ensureError(error), getChatSyncErrorTitle(), { notify: true });
    }
};

const presentAcceptedSend = async (inputArguments: { host: MessageSendingHost; runtimeSignal: AbortSignal | null; activation: ConversationActivationSnapshot; conversation: Conversation; payload: ComposerPayload; enqueuedInput: AcceptedConversationInput; optimisticInputOrderingAnchor: number; composerTextForClearing: string; applyComposerSideEffects: boolean; scrollToBottomOnSend: boolean; onEffectiveSendCommitted?: (() => void) | undefined; afterAdmission?: PostAdmissionHook | null | undefined }): Promise<void> => {
    const { host, runtimeSignal, conversation, payload, enqueuedInput } = inputArguments;
    try {
        if (inputArguments.applyComposerSideEffects) host.services.getAttachmentManager().checkoutAttachments(payload.attachments);
        throwIfAborted(runtimeSignal, 'Accepted chat send presentation was aborted.');
        if (enqueuedInput.isDispatchableHead) {
            mountOptimisticInputUserMessage({
                conversation,
                inputId: enqueuedInput.inputId,
                acceptedAtMs: enqueuedInput.acceptedAtMs,
                orderingAnchorTimestamp: inputArguments.optimisticInputOrderingAnchor,
                text: payload.messageText || null,
                attachmentContent: payload.attachmentContent
            });
        }
        if (host.conversation.isConversationActivationCurrent(inputArguments.activation, conversation.id)) {
            const hasAttachmentSurface = payload.attachments.length > 0 || payload.attachmentContent.length > 0;
            await runWithAbortSignalScope([runtimeSignal, inputArguments.activation.signal], (signal) =>
                commitEffectiveSendVisualState(host, {
                    scrollToBottomOnSend: inputArguments.scrollToBottomOnSend && enqueuedInput.inputType === 'prompt' && enqueuedInput.isDispatchableHead,
                    composerTextForClearing: inputArguments.applyComposerSideEffects ? inputArguments.composerTextForClearing : null,
                    abortSignal: signal,
                    renderCurrentConversation: () => host.presentation.renderCurrentConversation(),
                    prepareComposerSurfaceForEffectiveSend: inputArguments.applyComposerSideEffects && hasAttachmentSurface ? (): void => host.presentation.renderAttachedFilesPreview() : undefined
                })
            );
            if (!runtimeSignal?.aborted && host.conversation.isConversationActivationCurrent(inputArguments.activation, conversation.id)) inputArguments.onEffectiveSendCommitted?.();
        }
        throwIfAborted(runtimeSignal);
        await refreshConversationListAfterSharedSync(host);
        throwIfAborted(runtimeSignal);
        refreshComposerState(host);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isAbortError(runtimeError)) host.platform.handleError(runtimeError, getChatSyncErrorTitle(), { notify: true });
    } finally {
        runPostAdmissionHook(host, conversation.id, inputArguments.afterAdmission);
    }
};

const sendMessageWithResolvedPayload = async (inputArguments: { host: MessageSendingHost; lockLease: SendLockLease; initialSendLockKey: string; payload: ComposerPayload; applyComposerSideEffects: boolean; scrollToBottomOnSend?: boolean; inputIntent?: ConversationInputIntent; beforeSend?: QueuedSendGuard | null | undefined; onAdmissionStarted?: (() => void) | undefined; afterAdmission?: PostAdmissionHook | null; abortSignal?: AbortSignal | null } & SendMessageOptions): Promise<QueuedSendOutcome> => {
    const host = inputArguments.host;
    const inputIntent = inputArguments.inputIntent ?? 'prompt';
    let payload = inputArguments.payload;
    const composerTextForClearing = payload.messageText;
    const attachmentManager = host.services.getAttachmentManager();
    if (resolveSendLockKey(host.conversation.getCurrentConversation()?.id) !== inputArguments.initialSendLockKey) return blockQueuedSend('conversation-mismatch');
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
    const revalidateSend = (): QueuedSendOutcome => {
        throwIfAborted(inputArguments.abortSignal, 'Queued chat send was aborted.');
        return runSendGuard();
    };
    let guardOutcome = revalidateSend();
    if (guardOutcome.status !== 'sent') return guardOutcome;
    await host.conversation.waitForPendingAgentModeUpdate();
    guardOutcome = revalidateSend();
    if (guardOutcome.status !== 'sent') return guardOutcome;
    const executionModelPreflight = resolveSendExecutionModelPreflight(host, conversation);
    if (executionModelPreflight.status === 'blocked') return executionModelPreflight.outcome;
    const modelPreflight = executionModelPreflight.plan;
    const executionAgentMode = host.conversation.resolveAgentModeForConversation(conversationId);
    const isWorkspaceCurrent = (): boolean => matchesSoaiLinkWorkspaceSnapshot(host.conversation.getCurrentConversation(), workspaceSnapshot);
    await host.conversation.commitPendingDeletesForConversation(conversation);
    guardOutcome = revalidateSend();
    if (guardOutcome.status !== 'sent') return guardOutcome;
    if (!host.conversation.getConversationById(conversationId)) return blockQueuedSend('conversation-mismatch');
    const mutationSnapshot = captureConversationMutationSnapshot(conversation);
    let didPersistConversation = false;
    try {
        if (isChatConversationSettingsWritable(conversation)) {
            applyChatExecutionModelStateToConversation(conversation, {
                primaryModelId: modelPreflight.primaryModelId,
                agentMode: executionAgentMode
            });
            await applyLockedUserInstructionForSend(host, conversation, conversationId);
        }
        guardOutcome = revalidateSend();
        if (guardOutcome.status !== 'sent') {
            restoreConversationMutationSnapshot(conversation, mutationSnapshot);
            return guardOutcome;
        }
        const resolvedSoaiLinkPayload = inputArguments.applyComposerSideEffects ? await resolveComposerSoaiLinks(host, conversationId, payload, inputArguments.abortSignal ?? null) : await resolvePayloadSoaiLinks(host, conversationId, payload, inputArguments.abortSignal ?? null);
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
        guardOutcome = revalidateSend();
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
        guardOutcome = revalidateSend();
        if (guardOutcome.status !== 'sent') {
            refreshComposerState(host);
            return guardOutcome;
        }
        inputArguments.onAdmissionStarted?.();
        attachmentManager.markDraftCommitStarted();
        const optimisticInputOrderingAnchor = resolveOptimisticInputOrderingAnchor(conversation);
        const runtimeSignal = host.platform.getRuntimeAbortSignal();
        const activation = host.conversation.captureConversationActivation();
        const enqueuedInput = await host.services.getConversationInputsManager().enqueue(conversationId, {
            intent: inputIntent === 'steer' ? 'steer' : 'queued',
            text: payload.messageText || null,
            sourceText: payload.sourceText || null,
            attachmentContent: payload.attachmentContent
        });
        await presentAcceptedSend({
            host,
            runtimeSignal,
            activation,
            conversation,
            payload,
            enqueuedInput,
            optimisticInputOrderingAnchor,
            composerTextForClearing,
            applyComposerSideEffects: inputArguments.applyComposerSideEffects,
            scrollToBottomOnSend: inputArguments.scrollToBottomOnSend === true,
            onEffectiveSendCommitted: inputArguments.onEffectiveSendCommitted,
            afterAdmission: inputArguments.afterAdmission
        });
        return QUEUED_SEND_SENT;
    } catch (error) {
        const coercedError = ensureError(error);
        if (isAbortError(coercedError)) {
            await recoverFailedSendSurface({ host, conversation, conversationId, mutationSnapshot, restoreConversation: !didPersistConversation });
            return QUEUED_SEND_ABORTED;
        }
        if (coercedError instanceof ChatExecutionModelPreflightBlockedError) {
            showChatExecutionModelPreflightBlockedError(coercedError.reason);
            await recoverFailedSendSurface({ host, conversation, conversationId, mutationSnapshot, restoreConversation: !didPersistConversation });
            return blockQueuedSend('stale');
        }
        if (isWorkspaceScopeChangedError(coercedError)) return blockSendForConversationMismatch({ host, conversation, mutationSnapshot, restoreConversation: !didPersistConversation, workspaceCurrent: false });
        await recoverFailedSendSurface({ host, conversation, conversationId, mutationSnapshot, restoreConversation: !didPersistConversation });
        throw coercedError;
    }
};

export { sendMessageWithResolvedPayload };
export type { ConversationInputIntent, PostAdmissionHook, QueuedSendGuard };
