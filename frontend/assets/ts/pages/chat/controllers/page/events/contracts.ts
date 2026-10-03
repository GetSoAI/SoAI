/* SoAI - Chat page events contracts [frontend/assets/ts/pages/chat/controllers/page/events/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatActionId, ChatComposerActionMode, ChatConfigurationTabId, ChatTurnAdmissionSnapshot, ComposerDraftSurfaceSnapshot } from '@features/chat/public.ts';
import type { GeometryPoint } from '@core/layout/elementGeometry.ts';
import type { ConversationInputComposerOutcome, QueueConversationInputOptions, SendMessageOptions } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

interface ChatSidebarPeekEventsPort {
    handlePointerOver(event: Event): void;
    handlePointerOut(event: Event): void;
    handlePointerDown(target: Element): void;
    handleKeydown(event: Event): void;
    dismiss(): void;
}

interface ChatRootShellEventsPort {
    ensureRootElement(): HTMLElement;
    dispatchDataAction(action: ChatActionId, actionElement: HTMLElement, event: Event): void;
    handleChatMessageHoverChange(messageId: string, hovering: boolean): void;
    handleAgentKeyDown(event: KeyboardEvent): boolean;
    hideConversationColorPicker(): void;
    collapseSidebarIfNarrowViewport(): void;
    handleMobileSidebarClickAway(target: Element): void;
    sidebarPeek: ChatSidebarPeekEventsPort;
    closeChatModelControlMenu(): void;
    handleChatModelControlSearchInput(input: HTMLInputElement): void;
    showNotification(message: string, type: 'error' | 'warning' | 'success' | 'info', duration?: number): void;
    runUiTask(operationId: string, task: () => Promise<void> | void): void;
}

interface ChatRootComposerEventsPort {
    resizeChatInput(element: Element): void;
    updateInputState(): void;
    updateEmptyStateInputHint(): void;
    resolveSoaiLinksFromInput(input: HTMLTextAreaElement, inputValue: string): Promise<void>;
    handleChatInputHistoryNavigation(input: HTMLTextAreaElement, direction: 'up' | 'down'): boolean;
    draft: {
        noteChanged(value: string): void;
        flush(reason: string): Promise<void>;
    };
    applyParameterValueFromElement(element: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement): void;
    handleFileUpload(event: Event): Promise<void>;
    handleFolderUpload(event: Event): Promise<void>;
    handleAgentModeSelectChange(event: Event): void;
    resolveSendMessageButton(): HTMLButtonElement | null;
    resolveComposerActionMode(): ChatComposerActionMode;
    resolveCurrentTurnAdmission(): ChatTurnAdmissionSnapshot | null;
    resolveSyncedCurrentTurnAdmission(): Promise<ChatTurnAdmissionSnapshot | null>;
    sendMessage(options?: SendMessageOptions): Promise<void>;
    queueConversationInputFromComposer(intent: 'queued' | 'steer', options?: QueueConversationInputOptions): Promise<ConversationInputComposerOutcome>;
    getComposerAttachmentCount(): number;
    isCurrentConversationStreaming(): boolean;
    isCtrlEnterSendRequired(): boolean;
}

interface ChatRootMessageEventsPort {
    resolveMessageIdForTarget(target: Element): string | null;
    saveEditedMessage(messageId: string): Promise<void>;
}

interface ChatRootConversationEventsPort {
    handleConversationTitleBlur(event: Event): Promise<void>;
    handleConversationListTitleBlur(event: Event): Promise<void>;
    updateConversationRenameDraft(value: string): void;
    saveConversationTitleRename(): Promise<void>;
    cancelConversationTitleRename(): void;
    saveConversationListTitleRename(): Promise<void>;
    cancelConversationListTitleRename(): void;
    isConversationSelectionActive(): boolean;
    exitConversationSelectMode(): void;
}

interface ChatRootHoldSession {
    move(current: GeometryPoint): void;
    release(current: GeometryPoint): void;
    cancel(showStatus: boolean): void;
}

interface ChatRootHoldShortcutsPort {
    openConfiguration(tabId: ChatConfigurationTabId, attentionTarget?: 'context-window'): void;
    canStartPushToTalk(): boolean;
    beginPushToTalk(button: HTMLButtonElement, start: GeometryPoint, draftSnapshot: ComposerDraftSurfaceSnapshot): ChatRootHoldSession | null;
    captureDraftSurface(): ComposerDraftSurfaceSnapshot;
}

interface ChatRootEventsHost {
    shell: ChatRootShellEventsPort;
    composer: ChatRootComposerEventsPort;
    messages: ChatRootMessageEventsPort;
    conversations: ChatRootConversationEventsPort;
    holdShortcuts: ChatRootHoldShortcutsPort;
}

export type { ChatRootEventsHost, ChatRootHoldShortcutsPort };
