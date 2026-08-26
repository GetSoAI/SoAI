/* SoAI - Shared frontend chat RAG ingestion service access [frontend/assets/ts/core/chat/ragIngestionServiceAccess.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_RAG_INGESTION_SERVICE_ID, type ChatRagIngestionServiceContract } from '@core/chat/protocols.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

const isChatRagIngestionService = <T>(value: T): value is T & ChatRagIngestionServiceContract => {
    return isObject(value) && 'getStatusForConversation' in value && 'start' in value && 'cancel' in value && 'subscribe' in value && isFunction(value.getStatusForConversation) && isFunction(value.start) && isFunction(value.cancel) && isFunction(value.subscribe);
};

const requireChatRagIngestionService = (): ChatRagIngestionServiceContract => {
    const service = resolveKernelService(CHAT_RAG_INGESTION_SERVICE_ID);
    if (!isChatRagIngestionService(service)) {
        throw new Error(`${CHAT_RAG_INGESTION_SERVICE_ID} must expose the chat RAG ingestion service contract`);
    }
    return service;
};

export { isChatRagIngestionService, requireChatRagIngestionService };
