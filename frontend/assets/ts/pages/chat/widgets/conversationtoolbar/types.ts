/* SoAI - Chat page conversation toolbar contracts [frontend/assets/ts/pages/chat/widgets/conversationtoolbar/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ConversationToolbarUiRefs {
    toolbarContainer: HTMLElement;
    collapsedLayer: HTMLElement;
    expandedLayer: HTMLElement;
    toolbarContent: HTMLElement;
    metricsContainer: HTMLElement;
    totalConversationsLabel: HTMLElement;
    totalConversationsIcon: HTMLElement;
    openArchivedButton: HTMLButtonElement;
    selectButton: HTMLElement;
    batchActionsContainer: HTMLElement;
    selectedCountLabel: HTMLElement;
    batchArchiveButton: HTMLButtonElement;
    batchCloneButton: HTMLButtonElement;
    batchDeleteButton: HTMLButtonElement;
    exitSelectButton: HTMLElement;
    collapsedChevronToggle: HTMLElement;
    expandedChevronToggle: HTMLElement;
    conversationsList: HTMLElement;
}

interface ConversationToolbarStrings {
    toolbarExpand: string;
    toolbarSelect: string;
    toolbarArchive: string;
    toolbarBatchArchive: string;
    toolbarBatchDelete: string;
    toolbarBatchClone: string;
    toolbarExitSelect: string;
}

export type { ConversationToolbarStrings, ConversationToolbarUiRefs };
