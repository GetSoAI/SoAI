/* SoAI - Chat attach modal linked knowledge types [frontend/assets/ts/pages/chat/controllers/modals/chatattach/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatAttachment } from '@features/chat/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

interface ChatAttachDraftAttachmentListElements {
    status: HTMLElement;
    summary: HTMLElement;
    list: HTMLElement;
}

interface ChatAttachUploadElements {
    dropzoneButton: HTMLButtonElement;
    filesButton: HTMLButtonElement;
    folderButton: HTMLButtonElement;
    draftList: ChatAttachDraftAttachmentListElements;
}

interface ChatAttachSoaiLinkElements {
    input: HTMLTextAreaElement;
    draftList: ChatAttachDraftAttachmentListElements;
}

interface ChatAttachKnowledgeElements {
    documentInput: HTMLInputElement;
    folderInput: HTMLInputElement;
    dropzoneButton: HTMLButtonElement;
    documentsButton: HTMLButtonElement;
    folderButton: HTMLButtonElement;
    importButton: HTMLButtonElement;
    reindexButton: HTMLButtonElement;
    progress: HTMLElement;
    summary: HTMLElement;
    list: HTMLElement;
}

type ChatAttachDraftAttachmentListEntry = {
    attachment: ChatAttachment;
    iconName: IconName;
    previewUrl: string | null;
};

export type { ChatAttachDraftAttachmentListElements, ChatAttachDraftAttachmentListEntry, ChatAttachKnowledgeElements, ChatAttachSoaiLinkElements, ChatAttachUploadElements };
