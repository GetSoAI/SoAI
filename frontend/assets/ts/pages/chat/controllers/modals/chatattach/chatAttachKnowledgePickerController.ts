/* SoAI - Chat attach modal knowledge picker controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachKnowledgePickerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readChatAttachKnowledgeCapabilities } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeCapabilitiesController.ts';
import type { ChatAttachKnowledgeElements } from '@pages/chat/controllers/modals/chatattach/types.ts';
import { openFilePicker } from '@pages/chat/controllers/modals/chatattach/view.ts';

const openKnowledgeDocumentsPicker = (elements: ChatAttachKnowledgeElements): void => {
    if (!readChatAttachKnowledgeCapabilities().documentsEnabled) {
        return;
    }
    openFilePicker(elements.documentInput);
};

const openKnowledgeFolderPicker = (elements: ChatAttachKnowledgeElements): void => {
    if (!readChatAttachKnowledgeCapabilities().foldersEnabled) {
        return;
    }
    openFilePicker(elements.folderInput);
};

const openKnowledgePrimaryPicker = (elements: ChatAttachKnowledgeElements): void => {
    if (readChatAttachKnowledgeCapabilities().documentsEnabled) {
        openKnowledgeDocumentsPicker(elements);
        return;
    }
    openKnowledgeFolderPicker(elements);
};

export { openKnowledgeDocumentsPicker, openKnowledgeFolderPicker, openKnowledgePrimaryPicker };
