/* SoAI - Authoritative knowledge attachment presentation and terminal notification state [frontend/assets/ts/features/chat/knowledgeAttachmentPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { KnowledgeAttachmentSummary } from '@core/api/contracts/webuiAttachmentContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

type KnowledgePresentation = {
    label: string;
    showSpinner: boolean;
};

type KnowledgeTerminalNotification = {
    message: string;
    type: NotificationType;
};

type KnowledgeIngestionIdentity = {
    clientBatchId: string | null;
    knowledgeAttachment: KnowledgeAttachmentSummary | null;
};

const resolveKnowledgeAttachmentPresentation = (summary: KnowledgeAttachmentSummary): KnowledgePresentation => {
    if (summary.processingState === 'cancelling') return { label: i18n.t('chat.ingestion.stage.cancelling'), showSpinner: true };
    if (summary.processingState === 'pending' || summary.processingState === 'running') {
        if ((summary.statusCounts['embedding'] ?? 0) > 0) return { label: i18n.t('chat.ingestion.stage.embedding'), showSpinner: true };
        if ((summary.statusCounts['chunking'] ?? 0) > 0) return { label: i18n.t('chat.ingestion.stage.chunking'), showSpinner: true };
        if ((summary.statusCounts['parsing'] ?? 0) > 0) return { label: i18n.t('chat.ingestion.stage.parsing'), showSpinner: true };
        if ((summary.statusCounts['fetching'] ?? 0) > 0) return { label: i18n.t('chat.ingestion.stage.fetching'), showSpinner: true };
        return { label: i18n.t('chat.ingestion.stage.queued'), showSpinner: true };
    }
    if (summary.processingState === 'ready') return { label: i18n.t('chat.attachments.status.ready'), showSpinner: false };
    if (summary.processingState === 'cancelled') return { label: i18n.t('chat.ingestion.terminal.cancelled'), showSpinner: false };
    return { label: i18n.t('chat.attachments.status.error'), showSpinner: false };
};

const sameLogicalAttachment = (left: KnowledgeAttachmentSummary, right: KnowledgeAttachmentSummary): boolean => {
    if (left.knowledgeAttachmentId && left.knowledgeAttachmentId === right.knowledgeAttachmentId) return true;
    return Boolean(left.clientBatchId && left.clientBatchId === right.clientBatchId);
};

const resolveKnowledgeAttachmentReconciliationId = (summary: KnowledgeAttachmentSummary): string => {
    if (summary.clientBatchId) return `knowledge-client:${summary.clientBatchId}`;
    return `knowledge:${summary.knowledgeAttachmentId}`;
};

const knowledgeSummaryMatchesIngestion = (summary: KnowledgeAttachmentSummary, ingestion: KnowledgeIngestionIdentity): boolean => {
    const knowledgeAttachmentId = ingestion.knowledgeAttachment?.knowledgeAttachmentId ?? null;
    const clientBatchId = ingestion.knowledgeAttachment?.clientBatchId ?? ingestion.clientBatchId;
    return (knowledgeAttachmentId !== null && summary.knowledgeAttachmentId === knowledgeAttachmentId) || (clientBatchId !== null && summary.clientBatchId === clientBatchId);
};

const selectLatestKnowledgeAttachmentSummary = (current: KnowledgeAttachmentSummary, incoming: KnowledgeAttachmentSummary): KnowledgeAttachmentSummary => {
    if (!sameLogicalAttachment(current, incoming)) return incoming;
    return incoming.attachmentRevision > current.attachmentRevision ? incoming : current;
};

const resolveKnowledgeTerminalNotification = (summary: KnowledgeAttachmentSummary): KnowledgeTerminalNotification | null => {
    if (summary.processingState === 'cancelled') return { message: i18n.t('chat.ingestion.terminal.cancelled'), type: 'info' };
    if (summary.processingState !== 'ready' && summary.processingState !== 'error') return null;
    const completed = summary.statusCounts['completed'] ?? 0;
    const failed = (summary.statusCounts['error'] ?? 0) + (summary.statusCounts['failed'] ?? 0);
    if (completed > 0 && failed > 0) return { message: i18n.t('chat.ingestion.terminal.mixed'), type: 'warning' };
    if (completed > 0 && summary.processingState === 'ready') return { message: i18n.t('chat.ingestion.terminal.ready'), type: 'success' };
    return { message: i18n.t('chat.ingestion.terminal.failed'), type: 'error' };
};

class KnowledgeTerminalNotificationRegistry {
    readonly #delivered = new Set<string>();

    take(summary: KnowledgeAttachmentSummary): KnowledgeTerminalNotification | null {
        const notification = resolveKnowledgeTerminalNotification(summary);
        if (notification === null || !summary.knowledgeAttachmentId) return null;
        const identity = `${summary.knowledgeAttachmentId}:${String(summary.attachmentRevision)}`;
        if (this.#delivered.has(identity)) return null;
        this.#delivered.add(identity);
        return notification;
    }
}

export { KnowledgeTerminalNotificationRegistry, knowledgeSummaryMatchesIngestion, resolveKnowledgeAttachmentPresentation, resolveKnowledgeAttachmentReconciliationId, resolveKnowledgeTerminalNotification, selectLatestKnowledgeAttachmentSummary };
