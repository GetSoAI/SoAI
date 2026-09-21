/* SoAI - Chat attach modal browse elements widget types [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachDraftAttachmentListElements } from '@pages/chat/controllers/modals/chatattach/types.ts';

interface ChatAttachBrowseElements {
    workspacePathInput: HTMLInputElement;
    workspacePathButton: HTMLButtonElement;
    searchInput: HTMLInputElement;
    results: HTMLElement;
    previewButton: HTMLButtonElement;
    attachButton: HTMLButtonElement;
    draftList: ChatAttachDraftAttachmentListElements;
}

export type { ChatAttachBrowseElements };
