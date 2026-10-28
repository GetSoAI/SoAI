/* SoAI - Chat feature UI manager [frontend/assets/ts/features/chat/ChatUIManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter, type ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { closeConversationInputModal, openConversationInputModal, syncConversationInputModal } from '@features/chat/chatuimanager/conversationInputModal.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { toggleToolActivityItem } from '@features/chat/chatuimanager/actions.ts';
import { clearAttachedFiles, forceScrollToBottom, getElement, isAutoScrollEnabled, requestOlderMessagesIfAtTop, revealElementFromUserAction, scheduleScrollToBottom, scrollIntoView, scrollToBottom, setAutoScrollEnabled, setElementVisibility, setupScrollListener, shouldAutoScrollAfterContentUpdate, updateMicrophoneAvailability } from '@features/chat/chatuimanager/dom.ts';
import { beginConversationScrollRestore, captureCurrentConversationScrollSnapshot, forgetConversationScrollSnapshot, prepareConversationScrollRestore, resolveConversationScrollRestoreCursor, setupConversationScrollSnapshotPersistence } from '@features/chat/chatuimanager/conversationScrollRestoration.ts';
import { isMainTimelineMeasurementAtBottom } from '@features/chat/mainTimelineScroll.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';
import { beginConversationTransition, completeConversationTransition, isConversationTransitionActive } from '@features/chat/chatuimanager/conversationTransition.ts';
import { setupAdvancedScrollPreview } from '@features/chat/chatuimanager/advancedScrollPreview.ts';
import { setupMessagesAreaInsets } from '@features/chat/chatuimanager/messagesAreaInsets.ts';
import { setupPreviewsContainerLayout } from '@features/chat/chatuimanager/previewLayout.ts';
import { hideSyncSpinner, showSyncSpinner } from '@features/chat/chatuimanager/syncSpinner.ts';
import { clearTimer, createChatUIManagerContext, disposeScrollRuntime } from '@features/chat/chatuimanager/state.ts';
import type { ChatComposerActionMode, ChatUIManagerContext, ChatUiManagerDependencies, ElementSelectorKey } from '@features/chat/chatuimanager/types.ts';
import { updateAudioRecordingPreview } from '@features/chat/chatuimanager/audioRecordingPreview.ts';
import { isConversationInputRemovable, resolveQueuedConversationInputs, updateInputQueuePreview } from '@features/chat/chatuimanager/inputQueuePreview.ts';
import type { AudioRecordingSnapshot } from '@features/chat/ChatAudioManager.ts';
import { resolveComposerControlState } from '@features/chat/chatuimanager/composerControlState.ts';
import { applyExecutionControls, updateAttachmentsPreview, updateInputState } from '@features/chat/chatuimanager/view.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import { setupChatChromeVisibilityRuntime } from '@features/chat/chatuimanager/chatChromeVisibilityRuntime.ts';

class ChatUIManager {
    #context: ChatUIManagerContext;

    constructor(dependencies: ChatUiManagerDependencies) {
        this.#context = createChatUIManagerContext(dependencies);
    }

    getElement(key: ElementSelectorKey): HTMLElement | null {
        return getElement(this.#context, key);
    }

    setPreviewVisibility(shouldShow: boolean): void {
        setElementVisibility(this.#context, 'preview', shouldShow);
    }

    initialize(): void {
        this.updateInputState();
        this.#context.dependencies.composition.applyTextZoom();
        this.setupScrollListener();
        this.#context.state.chatChromeVisibilityRuntime ??= setupChatChromeVisibilityRuntime(this.#context);
        this.#context.state.conversationScrollSnapshotPersistenceDisposer ??= setupConversationScrollSnapshotPersistence(this.#context);
        if (!this.#context.state.messagesAreaInsetsDisposer) {
            this.#context.state.messagesAreaInsetsDisposer = setupMessagesAreaInsets(this.#context);
        }
        setupPreviewsContainerLayout(this.#context, () => this.updateAttachmentsPreview());
        setupAdvancedScrollPreview(this.#context);
        this.updateMicrophoneAvailability();
    }

    updateMicrophoneAvailability(): void {
        updateMicrophoneAvailability(this.#context);
    }

    dispose(): void {
        this.#context.state.speechSetupAbortController?.abort();
        this.#context.state.speechSetupAbortController = null;
        this.#context.state.speechSetupSelection = null;
        closeConversationInputModal(this.#context, 'page-dispose', false);
        this.#context.state.chatChromeVisibilityRuntime?.dispose();
        this.#context.state.chatChromeVisibilityRuntime = null;
        this.#clearDisposer('conversationScrollSnapshotPersistenceDisposer');
        disposeScrollRuntime(this.#context);
        this.#clearDisposer('messagesAreaInsetsDisposer');
        this.#clearDisposer('attachedFilesPreviewLayoutDisposer');
        this.#clearDisposer('advancedScrollPreviewDisposer');
        this.#context.state.advancedScrollPreviewOverlay = null;
    }

    toggleSidebar(): void {
        const nextOpen = !this.#context.dependencies.sidebar.getSidebarOpen();
        this.#context.dependencies.sidebar.setSidebarOpen(nextOpen);
        this.#context.dependencies.composition.applySidebarState();
        this.#context.dependencies.drafts.saveChatState();
    }

    applyExecutionControls(): void {
        applyExecutionControls(this.#context);
        this.syncChatChromeVisibility();
    }

    resolveComposerActionMode(): ChatComposerActionMode {
        return resolveComposerControlState(this.#context).actionMode;
    }

    canStopComposerHandoff(): boolean {
        return resolveComposerControlState(this.#context).canStopHandoff;
    }

    noteUserStop(conversationId: string, requestId: string | null): void {
        this.#context.state.userStoppedTurn = { conversationId, requestId };
        this.applyExecutionControls();
    }

    updateInputState(): void {
        updateInputState(this.#context);
        this.syncChatChromeVisibility();
    }

    updateAttachmentsPreview(): void {
        updateAttachmentsPreview(this.#context);
    }

    syncChatChromeVisibility(): void {
        this.#context.state.chatChromeVisibilityRuntime?.sync();
    }

    updateInputQueuePreview(): void {
        const entries = resolveQueuedConversationInputs(this.#context);
        updateInputQueuePreview(this.#context, entries);
        syncConversationInputModal(this.#context, entries);
        this.applyExecutionControls();
    }

    openConversationInput(conversationId: string, inputId: string): Promise<void> {
        return openConversationInputModal(this.#context, () => this.resolveModals(), conversationId, inputId);
    }

    canRemoveConversationInput(conversationId: string, inputId: string): boolean {
        if (conversationId !== this.#context.dependencies.session.getCurrentConversationId()) return false;
        return resolveQueuedConversationInputs(this.#context).some((entry) => entry.inputId === inputId && isConversationInputRemovable(entry.state));
    }

    handleConversationChanged(conversationId: string | null): void {
        const session = this.#context.state.conversationInputModal;
        if (session !== null && session.conversationId !== conversationId) closeConversationInputModal(this.#context, 'conversation-changed', true);
    }

    updateAudioRecordingPreview(snapshot: AudioRecordingSnapshot): void {
        updateAudioRecordingPreview(this.#context, snapshot);
    }

    beginConversationTransition(transitionId: number): void {
        beginConversationTransition(this.#context, transitionId);
        this.#context.state.chatChromeVisibilityRuntime?.reset();
    }

    completeConversationTransition(transitionId: number): void {
        completeConversationTransition(this.#context, transitionId);
        this.#context.state.chatChromeVisibilityRuntime?.reset();
    }

    isConversationTransitionActive(): boolean {
        return isConversationTransitionActive(this.#context);
    }

    toggleToolActivityItem(header: Element | null): Promise<void> {
        return toggleToolActivityItem(this.#context, header);
    }

    clearAttachedFiles(): void {
        clearAttachedFiles(this.#context);
    }

    setupScrollListener(): void {
        setupScrollListener(this.#context);
    }

    requestOlderMessagesIfAtTop(): void {
        requestOlderMessagesIfAtTop(this.#context);
    }

    scrollToBottom(): void {
        scrollToBottom(this.#context);
    }

    rememberCurrentConversationScrollPosition(): void {
        captureCurrentConversationScrollSnapshot(this.#context);
    }

    prepareConversationScrollRestore(conversationId: string): boolean {
        return prepareConversationScrollRestore(this.#context, conversationId);
    }

    resolveConversationScrollRestoreCursor(conversationId: string): MessageCursor | null {
        return resolveConversationScrollRestoreCursor(this.#context, conversationId);
    }

    restoreConversationScrollPosition(): void {
        const messagesArea = this.#context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
        if (!(messagesArea instanceof HTMLElement)) return;
        beginConversationScrollRestore(this.#context, messagesArea, (cancelled) => {
            const settledMessagesArea = this.#context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
            if (!(settledMessagesArea instanceof HTMLElement)) return;
            const atBottom = isMainTimelineMeasurementAtBottom({ clientHeight: settledMessagesArea.clientHeight, scrollHeight: settledMessagesArea.scrollHeight, scrollTop: settledMessagesArea.scrollTop });
            this.setAutoScrollEnabled(atBottom);
            if (!cancelled) captureCurrentConversationScrollSnapshot(this.#context);
            this.requestOlderMessagesIfAtTop();
        });
    }

    forgetConversationScrollPosition(conversationId: string): void {
        forgetConversationScrollSnapshot(this.#context, conversationId);
    }

    forceScrollToBottom(behavior: ScrollBehavior = 'instant'): void {
        forceScrollToBottom(this.#context, behavior);
    }

    setAutoScrollEnabled(enabled: boolean): void {
        setAutoScrollEnabled(this.#context, enabled);
    }

    isAutoScrollEnabled(): boolean {
        return isAutoScrollEnabled(this.#context);
    }

    shouldAutoScrollAfterContentUpdate(): boolean {
        return shouldAutoScrollAfterContentUpdate(this.#context);
    }

    scheduleScrollToBottom(delayMs: number = 50): void {
        scheduleScrollToBottom(this.#context, delayMs);
    }

    scrollIntoView(target: Element | null, options: ScrollIntoViewOptions = {}): void {
        scrollIntoView(target, options);
    }

    revealElementFromUserAction(target: Element | null, options: ScrollIntoViewOptions = {}): void {
        revealElementFromUserAction(this.#context, target, options);
    }

    clearTimer(timer: number | null | undefined): void {
        clearTimer(this.#context, timer);
    }

    toggleConfiguration(force: boolean | null = null): void {
        this.resolveModals().toggle(CHAT_CONFIGURATION_MODAL_ID, force);
    }

    resolveModals(): ModalPresenterApi {
        if (this.#context.state.modalPresenter) {
            return this.#context.state.modalPresenter;
        }

        this.#context.state.modalPresenter = requireModalPresenter();
        return this.#context.state.modalPresenter;
    }

    showSyncSpinner(): void {
        showSyncSpinner(this.#context);
    }

    hideSyncSpinner(): void {
        hideSyncSpinner(this.#context);
    }

    #clearDisposer(disposerKey: 'conversationScrollSnapshotPersistenceDisposer' | 'messagesAreaInsetsDisposer' | 'attachedFilesPreviewLayoutDisposer' | 'advancedScrollPreviewDisposer'): void {
        this.#context.state[disposerKey]?.();
        this.#context.state[disposerKey] = null;
    }
}

export { ChatUIManager };
export type { ChatUiManagerDependencies };
