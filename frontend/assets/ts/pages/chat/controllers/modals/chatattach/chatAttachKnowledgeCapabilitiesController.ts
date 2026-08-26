/* SoAI - Chat attach modal knowledge capabilities controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachKnowledgeCapabilitiesController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeSource } from '@pages/chat/controllers/modals/chatattach/service.ts';

type ChatAttachKnowledgeCapabilities = {
    documentsEnabled: boolean;
    foldersEnabled: boolean;
};

const readChatAttachKnowledgeCapabilities = (): ChatAttachKnowledgeCapabilities => {
    return {
        documentsEnabled: true,
        foldersEnabled: true
    };
};

const isChatAttachKnowledgeSourceEnabled = (capabilities: ChatAttachKnowledgeCapabilities, source: KnowledgeSource): boolean => {
    return source === 'document' ? capabilities.documentsEnabled : capabilities.foldersEnabled;
};

export { isChatAttachKnowledgeSourceEnabled, readChatAttachKnowledgeCapabilities };
export type { ChatAttachKnowledgeCapabilities };
