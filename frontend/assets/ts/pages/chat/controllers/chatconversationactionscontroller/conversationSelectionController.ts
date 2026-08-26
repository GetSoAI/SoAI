/* SoAI - Canonical chat conversation selection lifecycle [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/conversationSelectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { beginLoadingButtonWithClear } from '@core/ui/loadingbuttons/service.ts';
import { resolveReusableNewConversationId, type Conversation } from '@features/chat/public.ts';
import { awaitConversationLoadingVisualCommit, hydrateSelectedConversationAfterActivation, isConversationActivationCurrent, isConversationActivationRedundant, prepareSelectedConversationHydrationState, renderActivatedConversationWindow, schedulePostHydrationConversationPreparation } from '@pages/chat/controllers/chatconversationactionscontroller/activationPostCommitController.ts';
import type { ConversationOperationOptions } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';
import { CONVERSATION_SWITCH_OPERATION_ID, NAVIGATION_OPERATION_ID, completeDraftTransfer, createOperationDependencies, enqueueOperation } from '@pages/chat/controllers/chatconversationactionscontroller/conversationOperationExecutionController.ts';
import { collapseSidebarIfNarrowViewport, commitConversationClearOperation, commitConversationSwitchOperation } from '@pages/chat/controllers/chatconversationactionscontroller/operations.ts';
import { cancelConversationRenameState } from '@pages/chat/controllers/chatconversationactionscontroller/service.ts';
import type { ChatConversationActionsControllerRuntime, ComposerDraftManager } from '@pages/chat/controllers/chatconversationactionscontroller/types.ts';
import type { ConversationActivationSnapshot } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';

type ComposerDraftTransfer = ReturnType<ComposerDraftManager['beginComposerTransfer']>;

const releasePreviousConversationTranscript = (runtime: ChatConversationActionsControllerRuntime, previousConversationId: string | null): void => {
    if (previousConversationId === null || runtime.state.getCurrentConversationId() === previousConversationId) return;
    const previousConversation = runtime.state.getConversation(previousConversationId);
    if (previousConversation !== null) runtime.getMessageDeleteManager()?.resumePausedDeletesForConversation(previousConversation);
    runtime.storageManager.evictConversationMessages(previousConversationId);
};

const isClearActivationCurrent = (runtime: ChatConversationActionsControllerRuntime, activation: ConversationActivationSnapshot): boolean => {
    return runtime.concurrencyScope.isConversationActivationSnapshotLive(activation) && runtime.state.getCurrentConversationId() === null;
};

const finishConversationPresentation = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string, activation: ConversationActivationSnapshot, options: ConversationOperationOptions, isVisualActivation: boolean): Promise<void> => {
    if (options.syncRoute !== false) {
        await runtime.host.navigation.replaceConversationRoute(conversationId, { signal: activation.signal });
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
    }
    if (isVisualActivation) {
        await renderActivatedConversationWindow(runtime);
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
        runtime.host.view.invalidateChatMarkup('list');
        await runtime.host.view.refreshConversationListAndHeader();
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
    }
    runtime.uiManager.applyExecutionControls();
    runtime.host.view.applyInputActionVisibility();
};

const activateConversationById = async (runtime: ChatConversationActionsControllerRuntime, conversationId: string, options: ConversationOperationOptions = {}, activationSnapshot?: ConversationActivationSnapshot): Promise<void> => {
    const activation = activationSnapshot ?? runtime.concurrencyScope.beginConversationActivation();
    if (!runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)) return;
    if (!runtime.state.hasConversation(conversationId)) throw new Error(`Conversation not found: ${conversationId}`);
    const isVisualActivation = options.refreshUi !== false;
    const previousConversationId = runtime.state.getCurrentConversationId();
    let transitionActive = isVisualActivation;
    let draftTransfer: ComposerDraftTransfer | null = null;
    if (transitionActive) runtime.uiManager.beginConversationTransition(activation.sequence);
    try {
        cancelConversationRenameState(runtime.host, runtime.state);
        commitConversationSwitchOperation(createOperationDependencies(runtime), conversationId);
        const shouldHydrate = prepareSelectedConversationHydrationState(runtime, conversationId, isVisualActivation);
        draftTransfer = runtime.getComposerDraftManager()?.beginComposerTransfer(conversationId, { mode: options.transferMode ?? 'restore', signal: activation.signal }) ?? null;
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
        if (isVisualActivation) {
            runtime.host.view.invalidateChatMarkup('current');
            await runtime.host.view.renderCurrentConversation();
            if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
            await awaitConversationLoadingVisualCommit(runtime, conversationId, activation);
            if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
        }
        const hydrationResult = shouldHydrate ? await hydrateSelectedConversationAfterActivation(runtime, conversationId, activation) : 'ready';
        if (hydrationResult === 'cancelled' || !isConversationActivationCurrent(runtime, conversationId, activation)) return;
        if (!shouldHydrate) runtime.state.setSelectedConversationHydrationState({ conversationId, status: 'idle' });
        await completeDraftTransfer(draftTransfer);
        draftTransfer = null;
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
        await finishConversationPresentation(runtime, conversationId, activation, options, isVisualActivation);
        if (!isConversationActivationCurrent(runtime, conversationId, activation)) return;
        if (hydrationResult === 'ready' && shouldHydrate) schedulePostHydrationConversationPreparation(runtime, conversationId, activation);
        runtime.chatStreamingController.refreshCurrentConversationActivityClock();
        if (transitionActive) {
            transitionActive = false;
            runtime.uiManager.completeConversationTransition(activation.sequence);
        }
    } finally {
        draftTransfer?.cancel();
        if (transitionActive) runtime.uiManager.completeConversationTransition(activation.sequence);
        releasePreviousConversationTranscript(runtime, previousConversationId);
    }
};

const clearConversationSelection = async (runtime: ChatConversationActionsControllerRuntime, options: ConversationOperationOptions = {}): Promise<void> => {
    const activation = runtime.concurrencyScope.beginConversationActivation();
    const isVisualActivation = options.refreshUi !== false;
    let transitionActive = isVisualActivation;
    if (transitionActive) runtime.uiManager.beginConversationTransition(activation.sequence);
    const previousConversationId = runtime.state.getCurrentConversationId();
    let draftTransfer: ComposerDraftTransfer | null = null;
    try {
        cancelConversationRenameState(runtime.host, runtime.state);
        commitConversationClearOperation(createOperationDependencies(runtime));
        draftTransfer = runtime.getComposerDraftManager()?.beginComposerTransfer(null, { mode: 'restore', signal: activation.signal }) ?? null;
        await completeDraftTransfer(draftTransfer);
        if (!isClearActivationCurrent(runtime, activation)) return;
        if (options.syncRoute !== false) {
            await runtime.host.navigation.replaceConversationRoute(null, { signal: activation.signal });
            if (!isClearActivationCurrent(runtime, activation)) return;
        }
        if (isVisualActivation) {
            runtime.host.view.invalidateChatMarkup('both');
            await runtime.host.view.refreshConversationsUI();
            if (!isClearActivationCurrent(runtime, activation)) return;
        }
        if (transitionActive) {
            transitionActive = false;
            runtime.uiManager.completeConversationTransition(activation.sequence);
        }
    } finally {
        draftTransfer?.cancel();
        if (transitionActive) runtime.uiManager.completeConversationTransition(activation.sequence);
        releasePreviousConversationTranscript(runtime, previousConversationId);
    }
};

const createConversation = async (runtime: ChatConversationActionsControllerRuntime, options: ConversationOperationOptions = {}, activationSnapshot?: ConversationActivationSnapshot): Promise<Conversation | null> => {
    const activation = activationSnapshot ?? runtime.concurrencyScope.beginConversationActivation();
    let conversation: Conversation | null;
    try {
        conversation = await runtime.conversationManager.createNewConversation();
    } catch (error) {
        if (isAbortError(error) || !runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)) return null;
        throw error;
    }
    runtime.storageManager.saveChatState();
    if (!runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)) return null;
    await activateConversationById(runtime, conversation.id, options, activation);
    return isConversationActivationCurrent(runtime, conversation.id, activation) ? conversation : null;
};

const switchConversationById = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): void => {
    if (!runtime.state.hasConversation(conversationId) || isConversationActivationRedundant(runtime, conversationId)) return;
    const activation = runtime.concurrencyScope.beginConversationActivation();
    const activationPromise = activateConversationById(runtime, conversationId, {}, activation);
    enqueueOperation(runtime, CONVERSATION_SWITCH_OPERATION_ID, {
        scope: 'chat:switchConversation',
        task: async () => {
            await activationPromise;
        },
        logMessage: 'Conversation switch failed',
        errorMessage: i18n.t('chat.conversation.switchFailed'),
        shouldNotifyError: () => runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)
    });
};

const openConversationEnsuringLoaded = (runtime: ChatConversationActionsControllerRuntime, conversationId: string): void => {
    if (!conversationId) return;
    const activation = runtime.concurrencyScope.beginConversationActivation();
    enqueueOperation(runtime, NAVIGATION_OPERATION_ID, {
        scope: 'chat:openArchivedConversation',
        task: async () => {
            if (!runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)) return;
            await runtime.conversationManager.ensureConversationLoaded(conversationId);
            if (!runtime.concurrencyScope.isConversationActivationSnapshotLive(activation)) return;
            await activateConversationById(runtime, conversationId, {}, activation);
        },
        logMessage: 'Archived conversation open failed',
        errorMessage: i18n.t('chat.errors.conversationLoadFailed')
    });
};

const openOrCreateNewConversation = async (runtime: ChatConversationActionsControllerRuntime): Promise<string | null> => {
    const reusableConversationId = resolveReusableNewConversationId(runtime.state.getConversations(), i18n.t('chat.conversation.newTitle'));
    if (reusableConversationId === null) return (await createConversation(runtime, { transferMode: 'restore' }))?.id ?? null;
    await activateConversationById(runtime, reusableConversationId, { transferMode: 'restore' });
    return reusableConversationId;
};

const handleNewConversationClick = (runtime: ChatConversationActionsControllerRuntime, actionElement: HTMLElement | null = null): void => {
    const button = actionElement instanceof HTMLButtonElement ? actionElement : null;
    const clearLoading = button === null ? null : beginLoadingButtonWithClear(button);
    enqueueOperation(runtime, NAVIGATION_OPERATION_ID, {
        scope: 'chat:createConversation',
        task: async () => {
            try {
                const conversationId = await openOrCreateNewConversation(runtime);
                if (conversationId !== null) await runtime.host.view.revealConversationInList(conversationId);
            } finally {
                clearLoading?.();
            }
        },
        logMessage: 'Conversation creation failed',
        errorMessage: i18n.t('chat.conversation.createFailed')
    });
    collapseSidebarIfNarrowViewport(createOperationDependencies(runtime));
};

export { activateConversationById, clearConversationSelection, createConversation, handleNewConversationClick, openConversationEnsuringLoaded, switchConversationById };
