/* SoAI - Conversation PDF export task lifecycle [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfTaskController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TaskResponse } from '@core/api/contracts/taskContracts.ts';
import { decodeSystemInfo } from '@core/api/contracts/systemContracts.ts';
import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { getWebUiUserCancellationReason } from '@core/tasks/cancellationReasons.ts';
import { isCancelledTaskStatus, isTerminalTaskStatus } from '@core/tasks/operationPayloads.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import type { ConversationPdfExportAcceptedResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { buildConversationExportCoverData } from '@features/chat/public.ts';
import { buildConversationPdfExportDocument } from '@pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfDocumentController.ts';
import { CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS, CONVERSATION_EXPORT_TASK_POLL_INTERVAL_MS } from '@pages/chat/controllers/chatmessagesendingcontroller/constants.ts';
import type { Conversation, MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';

const activeConversationPdfExports = new Set<string>();

const resolveTaskFailureMessage = (task: TaskResponse): string => {
    if (task.errorType === 'pdf_browser_unavailable') {
        return i18n.t('chat.export.pdf.error.browserUnavailable');
    }
    switch (task.errorCode) {
        case 409:
            return i18n.t('chat.export.pdf.error.conversationChanged');
        case 413:
            return i18n.t('chat.export.pdf.error.tooLarge');
        case 422:
            return i18n.t('chat.export.pdf.error.invalidRequest');
        default:
            return i18n.t('chat.export.pdf.failed');
    }
};

const resolveSoaiVersion = async (signal: AbortSignal | null): Promise<string | null> => {
    try {
        const info = await requestWebSocketSnapshotRecord('system.info', null, signal === null ? {} : { signal });
        return decodeSystemInfo(info).soaiVersion;
    } catch (error) {
        errorHandler.debug('ConversationPdfExport', 'SoAI version lookup failed for the export cover', ensureError(error));
        return null;
    }
};

const wait = async (host: MessageSendingHost, delayMs: number): Promise<void> => {
    const timerWindow = host.platform.getDocument().defaultView;
    const signal = host.platform.getRuntimeAbortSignal();
    if (signalAborted(signal)) {
        throw new DOMException(i18n.t('chat.export.pdf.cancelled'), 'AbortError');
    }
    await waitForTimerDelay(timerWindow, delayMs, signal);
    if (signalAborted(signal)) {
        throw new DOMException(i18n.t('chat.export.pdf.cancelled'), 'AbortError');
    }
};

const cancelPdfExportTask = async (host: MessageSendingHost, taskId: string): Promise<void> => {
    try {
        await host.services.getChatApi().system.cancelTask(taskId, getWebUiUserCancellationReason());
    } catch (error) {
        errorHandler.warn('ConversationPdfExport', 'Failed to cancel accepted PDF export task', ensureError(error), { context: { taskId } });
    }
};

const waitForPdfExportTask = async (host: MessageSendingHost, taskId: string): Promise<void> => {
    const signal = host.platform.getRuntimeAbortSignal();
    const deadlineMs = Date.now() + CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS;
    while (true) {
        if (signalAborted(signal)) {
            await cancelPdfExportTask(host, taskId);
            throw new DOMException(i18n.t('chat.export.pdf.cancelled'), 'AbortError');
        }
        const task = await host.services.getChatApi().tasks.get(taskId, signal === null ? {} : { signal });
        if (isTerminalTaskStatus(task.status)) {
            if (isCancelledTaskStatus(task.status)) {
                throw new DOMException(i18n.t('chat.export.pdf.cancelled'), 'AbortError');
            }
            if (task.status !== 'completed') {
                throw new Error(resolveTaskFailureMessage(task));
            }
            return;
        }
        if (Date.now() >= deadlineMs) {
            await cancelPdfExportTask(host, taskId);
            throw new Error(i18n.t('chat.export.pdf.error.timedOut'));
        }
        await wait(host, CONVERSATION_EXPORT_TASK_POLL_INTERVAL_MS);
    }
};

const runConversationPdfExportTask = async (host: MessageSendingHost, accepted: ConversationPdfExportAcceptedResponse, fallbackFilename: string): Promise<void> => {
    const taskId = accepted.taskId;
    await waitForPdfExportTask(host, taskId);
    const downloadSignal = host.platform.getRuntimeAbortSignal();
    if (signalAborted(downloadSignal)) {
        throw new DOMException(i18n.t('chat.export.pdf.cancelled'), 'AbortError');
    }
    const response = await host.services.getChatApi().webui.chat.exportPdf.download(taskId, downloadSignal === null ? { rawResponse: true } : { rawResponse: true, signal: downloadSignal });
    if (!(response instanceof Response)) {
        throw new Error(i18n.t('chat.export.pdf.failed'));
    }
    await downloadAuthenticatedResponse(response, { filename: fallbackFilename });
};

const runExclusiveConversationPdfExport = async (host: MessageSendingHost, conversationId: string, action: () => Promise<void>): Promise<void> => {
    if (activeConversationPdfExports.has(conversationId)) {
        host.platform.feedback.show(i18n.t('chat.export.pdf.alreadyRunning'), 'info');
        return;
    }
    activeConversationPdfExports.add(conversationId);
    try {
        await action();
    } finally {
        activeConversationPdfExports.delete(conversationId);
    }
};

const startAndDownloadConversationPdfExport = async (host: MessageSendingHost, conversation: Conversation, title: string, exportedAt: Date, defaultModel: string | null): Promise<void> => {
    const coverData = buildConversationExportCoverData(conversation, {
        defaultModel,
        resolveModel: (modelId) => host.model.resolveModelDescriptor(modelId),
        exportedAt
    });
    const soaiVersion = await resolveSoaiVersion(host.platform.getRuntimeAbortSignal());
    const documentPayload = await buildConversationPdfExportDocument(host, {
        conversation,
        title,
        exportedAt,
        coverData,
        soaiVersion
    });
    const uploadSignal = host.platform.getRuntimeAbortSignal();
    const fallbackFilename = `${generateSecureId({ prefix: `chat-${conversation.id}`, separator: '-' })}.pdf`;
    const accepted = await host.services.getChatApi().webui.chat.exportPdf.start(
        documentPayload.file,
        {
            sizeBytes: String(documentPayload.file.size),
            title,
            exportDate: documentPayload.exportDate,
            smallLogoDataUri: documentPayload.smallLogoDataUri,
            conversationId: conversation.id,
            expectedLastModifiedAtMs: String(conversation.updatedAt),
            coverHtml: documentPayload.coverHtml,
            coverSha256: documentPayload.coverSha256,
            footerNoteLabel: i18n.t('chat.export.pdf.exportedNote'),
            footerPagesLabel: i18n.t('chat.export.pdf.footerPages'),
            htmlSha256: documentPayload.htmlSha256
        },
        uploadSignal === null ? { timeoutMs: CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS } : { signal: uploadSignal, timeoutMs: CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS }
    );
    await runConversationPdfExportTask(host, accepted, fallbackFilename);
};

export { resolveTaskFailureMessage, runExclusiveConversationPdfExport, startAndDownloadConversationPdfExport };
