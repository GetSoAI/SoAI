/* SoAI - Chat feature upload progress [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/uploadProgress.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { requireTaskOperationsApi } from '@core/tasks/serviceAccess.ts';
import type { RagIngestionStatus } from '@features/chat/ingestion/types.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

const buildProgressKey = (conversationId: string): string => `rag-ingestion:${conversationId}`;

const resolveProgressDetails = (status: RagIngestionStatus): string => {
    if (status.failed > 0 && status.lastError) {
        return status.lastError;
    }
    if (status.state === 'submitted') {
        return i18n.t('chat.ingestion.filesSubmitted');
    }
    if (status.state === 'cancelled') {
        return i18n.t('chat.ingestion.cancelled');
    }
    if (status.state === 'paused') {
        return i18n.t('chat.ingestion.status.paused', {
            completed: status.succeeded,
            total: status.total,
            queued: status.queued,
            'in_flight': status.inFlight,
            failed: status.failed,
            skipped: status.skipped
        });
    }
    return i18n.t('chat.ingestion.status.running', {
        completed: status.succeeded,
        total: status.total,
        queued: status.queued,
        'in_flight': status.inFlight,
        failed: status.failed,
        skipped: status.skipped
    });
};

const resolveProgressPercent = (status: RagIngestionStatus): number => {
    if (status.total <= 0) {
        return status.state === 'submitted' ? 100 : 0;
    }
    if (status.state === 'submitted') {
        return 100;
    }
    const processed = status.succeeded + status.failed + status.skipped;
    return Math.round(clampNumber((processed / status.total) * 100, 0, 99));
};

const syncRagUploadProgress = (conversationId: string | null, status: RagIngestionStatus | null, cancelHandler: (() => void) | null): void => {
    const normalizedConversationId = normalizeConversationId(conversationId) || null;
    if (!normalizedConversationId) {
        return;
    }
    const progressKey = buildProgressKey(normalizedConversationId);
    if (!status || status.conversationId !== normalizedConversationId) {
        requireTaskOperationsApi().removeLocalOperation(progressKey);
        return;
    }
    if (status.state === 'submitted' || status.state === 'cancelled') {
        requireTaskOperationsApi().removeLocalOperation(progressKey);
        return;
    }
    requireTaskOperationsApi().upsertLocalOperation({
        id: progressKey,
        type: 'rag-document-upload',
        pluginName: 'RAG',
        progress: resolveProgressPercent(status),
        cancelable: Boolean(cancelHandler),
        cancel: cancelHandler ?? undefined,
        meta: {
            convId: normalizedConversationId,
            displayName: i18n.t('chat.ingestion.title'),
            statusMessage: resolveProgressDetails(status),
            taskStatus: status.state
        }
    });
};

export { syncRagUploadProgress };
