/* SoAI - Chat feature RAG ingestion start [frontend/assets/ts/features/chat/ragingestion/ragIngestionStart.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isArray } from '@core/typeGuards.ts';
import { createChatUploadFileTooLargeMessage, getChatUploadFileSizeLimit } from '@features/chat/attachments/attachmentValidation.ts';
import { normalizeConversationId, type RagIngestionAttachmentSource, type RagIngestionStatus } from '@features/chat/public.ts';

type RagIngestionStartRequest = {
    conversationId: string;
    files: File[];
    attachmentSource: RagIngestionAttachmentSource;
};

type ValidatedRagIngestionStartRequest = {
    conversationId: string;
    files: File[];
    attachmentSource: RagIngestionAttachmentSource;
};

type RagIngestionStartInitializeResult = {
    status: RagIngestionStatus;
    resetQueue: boolean;
    resetInFlight: boolean;
    resetConversationPersisted: boolean;
};

const initializeStatusForIngestionStart = (existing: RagIngestionStatus | null, conversationId: string, fileCount: number): RagIngestionStartInitializeResult => {
    if (!existing || existing.state === 'submitted' || existing.state === 'cancelled') {
        return {
            status: {
                conversationId,
                clientBatchId: null,
                state: 'running',
                total: fileCount,
                queued: 0,
                inFlight: 0,
                succeeded: 0,
                failed: 0,
                skipped: 0,
                lastError: null,
                knowledgeAttachment: null
            },
            resetQueue: true,
            resetInFlight: true,
            resetConversationPersisted: true
        };
    }
    return {
        status: {
            ...existing,
            state: existing.state,
            total: existing.total + fileCount
        },
        resetQueue: false,
        resetInFlight: false,
        resetConversationPersisted: false
    };
};

type RagIngestionQueueValidationResult = {
    queuedFiles: File[];
    skippedCount: number;
    lastError: string | null;
};

const validateRagIngestionStartRequest = (inputArguments: RagIngestionStartRequest): ValidatedRagIngestionStartRequest | null => {
    const conversationId = normalizeConversationId(inputArguments.conversationId);
    if (!conversationId) {
        throw new Error('Conversation id is required for ingestion');
    }
    const files = isArray(inputArguments.files) ? inputArguments.files : [];
    if (files.length === 0) {
        return null;
    }
    return { conversationId, files, attachmentSource: inputArguments.attachmentSource };
};

const buildValidatedIngestionQueue = (files: readonly File[]): RagIngestionQueueValidationResult => {
    const sizeLimit = getChatUploadFileSizeLimit();
    const queuedFiles: File[] = [];
    let skippedCount = 0;
    let lastError: string | null = null;

    for (const file of files) {
        const fileName = toTrimmedString(file.name);
        if (!fileName) {
            skippedCount += 1;
            lastError = i18n.t('chat.upload.invalidFileName');
            continue;
        }
        if (file.size > sizeLimit.maxBytes) {
            skippedCount += 1;
            lastError = createChatUploadFileTooLargeMessage(fileName, sizeLimit);
            continue;
        }
        queuedFiles.push(file);
    }

    return { queuedFiles, skippedCount, lastError };
};

export { buildValidatedIngestionQueue, initializeStatusForIngestionStart, validateRagIngestionStartRequest };
export type { RagIngestionQueueValidationResult, RagIngestionStartInitializeResult, RagIngestionStartRequest, ValidatedRagIngestionStartRequest };
