/* SoAI - Chat attach modal linked knowledge refresh loader [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachKnowledgeRefreshController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { parseRagConfig, parseRagDocumentsPage, type RagConfig, type RagDocumentsPage } from '@features/chat/public.ts';
import type { ChatAttachKnowledgeRefreshHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';

const DOCUMENTS_LIMIT = 50;

type ChatAttachKnowledgeRefreshState = {
    config: RagConfig;
    page: RagDocumentsPage;
};

const loadChatAttachKnowledgeRefreshState = async (host: ChatAttachKnowledgeRefreshHost, conversationId: string, offset: number, signal: AbortSignal): Promise<ChatAttachKnowledgeRefreshState> => {
    const [configResult, documentsResult] = await Promise.allSettled([host.shared.api.webui.chat.rag.getConfig(conversationId, { signal }), host.shared.api.webui.chat.rag.listDocuments(conversationId, { limit: DOCUMENTS_LIMIT, offset, includeDocuments: true, signal })]);
    if (configResult.status === 'rejected') {
        throw ensureError(configResult.reason);
    }
    if (documentsResult.status === 'rejected') {
        throw ensureError(documentsResult.reason);
    }
    return {
        config: parseRagConfig(configResult.value),
        page: parseRagDocumentsPage(documentsResult.value)
    };
};

export { DOCUMENTS_LIMIT, loadChatAttachKnowledgeRefreshState };
