/* SoAI - Chat feature UI manager [frontend/assets/ts/features/chat/ChatUIManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter, type ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { toggleToolActivityItem } from '@features/chat/chatuimanager/actions.ts';
import { clearAttachedFiles, forceScrollToBottom, getElement, isAutoScrollEnabled, requestOlderMessagesIfAtTop, revealElementFromUserAction, scheduleScrollToBottom, scrollIntoView, scrollToBottom, setAutoScrollEnabled, setElementVisibility, setupScrollListener, shouldAutoScrollAfterContentUpdate, updateMicrophoneAvailability } from '@features/chat/chatuimanager/dom.ts';
import { beginConversationScrollRestore, captureCurrentConversationScrollSnapshot, forgetConversationScrollSnapshot, prepareConversationScrollRestore, resolveConversationScrollRestoreCursor } from '@features/chat/chatuimanager/conversationScrollRestoration.ts';
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
import { updateInputQueuePreview } from '@features/chat/chatuimanager/inputQueuePreview.ts';
import type { AudioRecordingSnapshot } from '@features/chat/ChatAudioManager.ts';
import { resolveComposerControlState } from '@features/chat/chatuimanager/composerControlState.ts';
import { applyExecutionControls, updateAttachmentsPreview, updateInputState } from '@features/chat/chatuimanager/view.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';

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
        this.#context.dependencies.sidebar.persistSidebarOpen(nextOpen);
        this.#context.dependencies.drafts.saveChatState();
    }

    applyExecutionControls(): void {
        applyExecutionControls(this.#context);
    }

    resolveComposerActionMode(): ChatComposerActionMode {
        return resolveComposerControlState(this.#context).actionMode;
    }

    updateInputState(): void {
        updateInputState(this.#context);
    }

    updateAttachmentsPreview(): void {
        updateAttachmentsPreview(this.#context);
    }

    updateInputQueuePreview(): void {
        updateInputQueuePreview(this.#context);
    }

    updateAudioRecordingPreview(snapshot: AudioRecordingSnapshot): void {
        updateAudioRecordingPreview(this.#context, snapshot);
    }

    beginConversationTransition(transitionId: number): void {
        beginConversationTransition(this.#context, transitionId);
    }

    completeConversationTransition(transitionId: number): void {
        completeConversationTransition(this.#context, transitionId);
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
        beginConversationScrollRestore(this.#context, messagesArea, () => {
            const settledMessagesArea = this.#context.dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_AREA);
            if (!(settledMessagesArea instanceof HTMLElement)) return;
            const atBottom = isMainTimelineMeasurementAtBottom({ clientHeight: settledMessagesArea.clientHeight, scrollHeight: settledMessagesArea.scrollHeight, scrollTop: settledMessagesArea.scrollTop });
            this.setAutoScrollEnabled(atBottom);
            captureCurrentConversationScrollSnapshot(this.#context);
            this.requestOlderMessagesIfAtTop();
        });
    }

    forgetConversationScrollPosition(conversationId: string): void {
        forgetConversationScrollSnapshot(this.#context, conversationId);
    }

    forceScrollToBottom(): void {
        forceScrollToBottom(this.#context);
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

    #clearDisposer(disposerKey: 'messagesAreaInsetsDisposer' | 'attachedFilesPreviewLayoutDisposer' | 'advancedScrollPreviewDisposer'): void {
        this.#context.state[disposerKey]?.();
        this.#context.state[disposerKey] = null;
    }
}

export { ChatUIManager };
export type { ChatUiManagerDependencies };
