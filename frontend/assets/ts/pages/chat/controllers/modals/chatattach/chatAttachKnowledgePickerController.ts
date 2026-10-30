/* SoAI - Chat attach modal knowledge picker controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachKnowledgePickerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readChatAttachKnowledgeCapabilities } from '@pages/chat/controllers/modals/chatattach/chatAttachKnowledgeCapabilitiesController.ts';

import { openAttachFilePicker, type AttachKnowledgeElements } from '@features/attachmodal/public.ts';

const openKnowledgeDocumentsPicker = (elements: AttachKnowledgeElements): void => {
    if (!readChatAttachKnowledgeCapabilities().documentsEnabled) {
        return;
    }
    openAttachFilePicker(elements.documentInput);
};

const openKnowledgeFolderPicker = (elements: AttachKnowledgeElements): void => {
    if (!readChatAttachKnowledgeCapabilities().foldersEnabled) {
        return;
    }
    openAttachFilePicker(elements.folderInput);
};

const openKnowledgePrimaryPicker = (elements: AttachKnowledgeElements): void => {
    if (readChatAttachKnowledgeCapabilities().documentsEnabled) {
        openKnowledgeDocumentsPicker(elements);
        return;
    }
    openKnowledgeFolderPicker(elements);
};

export { openKnowledgeDocumentsPicker, openKnowledgeFolderPicker, openKnowledgePrimaryPicker };
