/* SoAI - Chat page events contracts [frontend/assets/ts/pages/chat/controllers/page/events/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatActionId, ChatComposerActionMode, ChatTurnAdmissionSnapshot } from '@features/chat/public.ts';
import type { ConversationInputComposerOutcome, SendMessageOptions } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

interface ChatRootShellEventsPort {
    ensureRootElement(): HTMLElement;
    dispatchDataAction(action: ChatActionId, actionElement: HTMLElement, event: Event): void;
    handleChatMessageHoverChange(messageId: string, hovering: boolean): void;
    handleAgentKeyDown(event: KeyboardEvent): boolean;
    hideConversationColorPicker(): void;
    collapseSidebarIfNarrowViewport(): void;
    handleMobileSidebarClickAway(target: Element): void;
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
    queueConversationInputFromComposer(intent: 'queued' | 'steer'): Promise<ConversationInputComposerOutcome>;
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

interface ChatRootEventsHost {
    shell: ChatRootShellEventsPort;
    composer: ChatRootComposerEventsPort;
    messages: ChatRootMessageEventsPort;
    conversations: ChatRootConversationEventsPort;
}

export type { ChatRootEventsHost };
