/* SoAI - Chat page activation post commit controller [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/activationPostCommitController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { awaitAnimationFrame } from '@core/runtime/animationFrames.ts';
import type { ChatConversationActionsControllerRuntime } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';
import type { ConversationActivationSnapshot } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';
import { APIError } from '@core/apiError.ts';

const isConversationActivationCurrent = (runtime: ChatConversationActionsControllerRuntime, conversationId: string, activation: ConversationActivationSnapshot): boolean => {
    return runtime.concurrencyScope.isConversationActivationSnapshotCurrent(activation, conversationId, runtime.state.getCurrentConversationId());
};

const isConversationActivationRedundant = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): boolean => {
    if (runtime.state.getCurrentConversationId() !== conversationId) {
        return false;
    }
    const hydrationState = runtime.state.getSelectedConversationHydrationState();
    if (hydrationState.conversationId !== conversationId) {
        return false;
    }
    if (hydrationState.status === 'loading') {
        return runtime.uiManager.isConversationTransitionActive();
    }
    return hydrationState.status === 'idle';
};

const presentConversationActivationFailure = (runtime: ChatConversationActionsControllerRuntime, conversationId: string, activation: ConversationActivationSnapshot): boolean => {
    if (!isConversationActivationCurrent(runtime, conversationId, activation)) {
        return false;
    }
    runtime.state.setSelectedConversationHydrationState({
        conversationId,
        status: 'error'
    });
    return true;
};

const prepareSelectedConversationHydrationState = (runtime: ChatConversationActionsControllerRuntime, conversationId: string, isVisualActivation: boolean): boolean => {
    const conversation = runtime.state.getConversation(conversationId);
    const shouldHydrate = runtime.conversationManager.isConversationPersisted(conversationId);
    if (shouldHydrate && conversation) {
        conversation.messages = [];
        conversation.messagesHydrated = false;
        delete conversation.history;
    }
    runtime.state.setSelectedConversationHydrationState({
        conversationId,
        status: isVisualActivation ? 'loading' : 'idle'
    });
    return shouldHydrate;
};

const renderActivatedConversationWindow = async (runtime: ChatConversationActionsControllerRuntime): Promise<void> => {
    runtime.host.view.invalidateChatMarkup('current');
    await runtime.host.view.renderCurrentConversation();
    runtime.chatStreamingController.refreshCurrentConversationActivityClock();
};

const awaitConversationLoadingVisualCommit = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string, activation: ConversationActivationSnapshot): Promise<void> => {
    if (!isConversationActivationCurrent(runtime, conversationId, activation)) {
        return;
    }
    runtime.host.view.flushDOMUpdates();
    try {
        await awaitAnimationFrame(activation.signal, 'Chat conversation loading visual commit aborted.');
    } catch (error) {
        if (isAbortError(error)) {
            return;
        }
        throw error;
    }
};

const syncActivatedConversationAdmission = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string): Promise<void> => {
    try {
        await runtime.chatStreamingController.syncConversationStatus(conversationId);
    } catch (error) {
        if (isAbortError(error)) {
            return;
        }
        const runtimeError = ensureError(error);
        errorHandler.warn('ChatConversationActionsController', 'Conversation admission status sync failed', runtimeError);
    }
};

const schedulePostHydrationConversationPreparation = (runtime: ChatConversationActionsControllerRuntime, conversationId: string, activation: ConversationActivationSnapshot): void => {
    runtime.host.workflow.runUiTask(`chat:postHydration:${conversationId}`, async () => {
        try {
            if (!isConversationActivationCurrent(runtime, conversationId, activation)) {
                return;
            }
            await runtime.host.view.prepareConversationMessages(conversationId);
            if (isConversationActivationCurrent(runtime, conversationId, activation)) {
                runtime.chatStreamingController.refreshCurrentConversationActivityClock();
            }
        } catch (error) {
            if (isAbortError(error) || !isConversationActivationCurrent(runtime, conversationId, activation)) {
                return;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('ChatConversationActionsController', 'Post-hydration conversation preparation failed', runtimeError);
            runtime.host.workflow.handleError?.(runtimeError, 'Post-hydration conversation preparation failed', { notify: false });
        }
    });
};

const hydrateSelectedConversationAfterActivation = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string, activation: ConversationActivationSnapshot): Promise<'ready' | 'error' | 'cancelled'> => {
    if (!runtime.conversationManager.isConversationPersisted(conversationId)) {
        runtime.state.setSelectedConversationHydrationState({ conversationId, status: 'idle' });
        return 'ready';
    }
    try {
        const scrollAnchor = runtime.uiManager.resolveConversationScrollRestoreCursor(conversationId);
        try {
            await runtime.storageManager.loadConversationMessages(conversationId, scrollAnchor === null ? { signal: activation.signal } : { signal: activation.signal, direction: 'around', anchor: scrollAnchor });
        } catch (error) {
            if (scrollAnchor === null || !(error instanceof APIError) || (error.status !== 400 && error.status !== 422)) throw error;
            errorHandler.warn('ChatConversationActionsController', 'Stored conversation scroll anchor is no longer available; loading the latest message window', error);
            runtime.uiManager.forgetConversationScrollPosition(conversationId);
            runtime.uiManager.setAutoScrollEnabled(true);
            await runtime.storageManager.loadConversationMessages(conversationId, { signal: activation.signal });
        }
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) {
            return 'cancelled';
        }
        await syncActivatedConversationAdmission(runtime, conversationId);
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) {
            return 'cancelled';
        }
        runtime.state.setSelectedConversationHydrationState({ conversationId, status: 'idle' });
    } catch (error) {
        if (isAbortError(error)) {
            return 'cancelled';
        }
        const runtimeError = ensureError(error);
        errorHandler.warn('ChatConversationActionsController', 'Conversation hydration failed', runtimeError);
        runtime.host.workflow.handleError?.(runtimeError, 'Conversation hydration failed', { notify: false });
        if (presentConversationActivationFailure(runtime, conversationId, activation)) {
            runtime.host.workflow.feedback.show(i18n.t('chat.errors.conversationLoadFailed'), 'error');
        }
        return 'error';
    }
    if (!isConversationActivationCurrent(runtime, conversationId, activation)) {
        return 'cancelled';
    }
    return 'ready';
};

export { awaitConversationLoadingVisualCommit, hydrateSelectedConversationAfterActivation, isConversationActivationCurrent, isConversationActivationRedundant, prepareSelectedConversationHydrationState, presentConversationActivationFailure, renderActivatedConversationWindow, schedulePostHydrationConversationPreparation };
