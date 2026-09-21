/* SoAI - Conversation export actions for chat message sending [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/conversationExportController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError, extractErrorCode } from '@core/errors/coerce.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { cloneStructured } from '@core/primitives/clone.ts';
import { createBusyDisabledToken, setBusyDisabledState, type BusyDisabledToken } from '@core/ui/controls/busyDisabledState.ts';
import { endLoadingButton } from '@core/ui/loadingbuttons/service.ts';
import { i18n } from '@core/i18n/index.ts';
import { resolveConversationDisplayTitleFromConversation } from '@features/chat/public.ts';
import { notifyExportResult, resolveCurrentConversationSelection, resolveSelectedSendModel } from '@pages/chat/controllers/chatmessagesendingcontroller/effects.ts';
import { runExclusiveConversationPdfExport, startAndDownloadConversationPdfExport } from '@pages/chat/controllers/chatmessagesendingcontroller/conversationExportPdfTaskController.ts';
import { CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS } from '@pages/chat/controllers/chatmessagesendingcontroller/constants.ts';
import type { ChatParameters, Conversation, MessageSendingHost } from '@pages/chat/controllers/chatmessagesendingcontroller/types.ts';
import { serializeChatParameters } from '@core/chat/parameters/chatRequestParameters.ts';

type HeaderExportLoadingState = {
    button: HTMLButtonElement;
    token: BusyDisabledToken;
};

type ConversationExportRequest = {
    conversationId: string | null;
    activeModel: string | null;
    parameters: ChatParameters;
};

const resolveHeaderExportButtons = (host: MessageSendingHost): HTMLButtonElement[] => {
    const buttons: HTMLButtonElement[] = [];
    for (const candidate of host.platform.pageDom.query('.export-btn')) {
        if (candidate instanceof HTMLButtonElement) {
            buttons.push(candidate);
        }
    }
    return buttons;
};

const isHeaderExportLoading = (host: MessageSendingHost, conversationId: string | null): boolean => {
    if (conversationId !== null) {
        return false;
    }
    return resolveHeaderExportButtons(host).some((button) => button.getAttribute('aria-busy') === 'true');
};

const beginHeaderExportLoading = (host: MessageSendingHost, conversationId: string | null): HeaderExportLoadingState[] => {
    if (conversationId !== null) {
        return [];
    }
    return resolveHeaderExportButtons(host).map((button) => ({
        button,
        token: setBusyDisabledState(button, {
            isBusy: true,
            createToken: createBusyDisabledToken,
            spinner: 'overlay'
        })
    }));
};

const endHeaderExportLoading = (host: MessageSendingHost, states: HeaderExportLoadingState[]): void => {
    for (const state of states) {
        endLoadingButton(state.button, state.token);
    }
    host.presentation.updateExportButtonVisibility();
};

const createConversationExportRequest = (host: MessageSendingHost, conversationId: string | null): ConversationExportRequest => {
    return {
        conversationId,
        activeModel: conversationId === null ? resolveSelectedSendModel(host) : null,
        parameters: cloneStructured(host.model.getParameters())
    };
};

const resolveConversationIdForExport = (host: MessageSendingHost, request: ConversationExportRequest): string | null => {
    if (request.conversationId === null) {
        const selection = resolveCurrentConversationSelection(host);
        return selection ? selection.conversationId : null;
    }
    return request.conversationId;
};

const isConversationExportBlockedByRunningState = (host: MessageSendingHost, request: ConversationExportRequest): boolean => {
    const conversationId = resolveConversationIdForExport(host, request);
    return conversationId !== null && host.conversation.isConversationExecuting(conversationId);
};

const shouldAbortConversationExportForRunningState = (host: MessageSendingHost, request: ConversationExportRequest): boolean => {
    if (!isConversationExportBlockedByRunningState(host, request)) {
        return false;
    }
    host.platform.feedback.show(i18n.t('chat.export.running'), 'info');
    return true;
};

const resolveConversationForExport = async (host: MessageSendingHost, request: ConversationExportRequest): Promise<Conversation | null> => {
    const resolvedConversationId = resolveConversationIdForExport(host, request);
    if (resolvedConversationId === null) {
        return null;
    }
    const initialConversation = host.conversation.getConversationById(resolvedConversationId);
    const isPersisted = host.services.getConversationManager().isConversationPersisted(resolvedConversationId);
    if (initialConversation !== null && isPersisted) {
        return await host.services.getStorageManager().readConversationSnapshot(resolvedConversationId, host.platform.getRuntimeAbortSignal() ?? undefined);
    }
    return initialConversation;
};

const createConversationExportSnapshot = async (host: MessageSendingHost, request: ConversationExportRequest): Promise<Conversation | null> => {
    const conversationId = resolveConversationIdForExport(host, request);
    if (conversationId === null) {
        return null;
    }
    const cachedConversation = host.conversation.getConversationById(conversationId);
    if (cachedConversation === null) {
        return null;
    }
    await host.conversation.commitPendingDeletesForConversation(cachedConversation);
    const conversation = await resolveConversationForExport(host, request);
    return conversation === null ? null : cloneStructured(conversation);
};

const resolveConversationExportTitle = (conversation: Conversation): string => {
    return resolveConversationDisplayTitleFromConversation(conversation, i18n.t('chat.conversation.untitled'));
};

const resolveConversationExportModel = (conversation: Conversation, request: ConversationExportRequest): string | null => {
    if (request.conversationId === null) {
        return request.activeModel;
    }
    return conversation.modelSettings.model;
};

const resolveConversationMessageCountForExport = (conversation: Conversation | null): number | null => {
    if (conversation === null) {
        return null;
    }
    if (conversation.history) {
        return conversation.history.totalCount;
    }
    return Math.max(conversation.messageCount ?? 0, conversation.messages.length);
};

const exportConversationJson = async (host: MessageSendingHost, request: ConversationExportRequest): Promise<void> => {
    if (shouldAbortConversationExportForRunningState(host, request)) {
        return;
    }
    const conversationId = resolveConversationIdForExport(host, request);
    if (conversationId === null) {
        notifyExportResult(host, false);
        return;
    }
    const conversation = host.conversation.getConversationById(conversationId);
    const messageCount = resolveConversationMessageCountForExport(conversation);
    if (messageCount === 0) {
        notifyExportResult(host, false);
        return;
    }
    if (conversation !== null) {
        await host.conversation.commitPendingDeletesForConversation(conversation);
    }
    if (shouldAbortConversationExportForRunningState(host, request)) {
        return;
    }
    const signal = host.platform.getRuntimeAbortSignal();
    const response = await host.services.getChatApi().webui.chat.exportJson.download(
        conversationId,
        {
            activeModel: request.activeModel,
            parameters: serializeChatParameters(request.parameters)
        },
        signal === null ? { rawResponse: true, timeoutMs: CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS } : { rawResponse: true, signal, timeoutMs: CONVERSATION_EXPORT_REQUEST_TIMEOUT_MS }
    );
    if (!(typeof Response === 'function' && response instanceof Response)) {
        throw new Error(i18n.t('chat.export.pdf.failed'));
    }
    await downloadAuthenticatedResponse(response, {
        filename: `${generateSecureId({ prefix: `chat-${conversationId}`, separator: '-' })}.json`
    });
    notifyExportResult(host, true);
};

const exportConversationJsonAfterPdfFailure = async (host: MessageSendingHost, request: ConversationExportRequest, error: Error): Promise<void> => {
    if (isAbortError(error)) {
        throw error;
    }
    host.platform.handleError(error, i18n.t('chat.export.pdf.title'), { notify: true });
    host.platform.feedback.show(i18n.t('chat.export.partialPdfJsonFallback'), 'info');
    await exportConversationJson(host, request);
};

const resolveConversationPdfExportError = (error: Error): Error => {
    if (extractErrorCode(error) === 'pdf_browser_unavailable') {
        return new Error(i18n.t('chat.export.pdf.error.browserUnavailable'), { cause: error });
    }
    return error;
};

const exportConversationPdf = async (host: MessageSendingHost, request: ConversationExportRequest): Promise<void> => {
    if (shouldAbortConversationExportForRunningState(host, request)) {
        return;
    }
    const conversation = await createConversationExportSnapshot(host, request);
    if (shouldAbortConversationExportForRunningState(host, request)) {
        return;
    }
    if (conversation === null) {
        notifyExportResult(host, false);
        return;
    }
    if (conversation.messages.length === 0) {
        notifyExportResult(host, false);
        return;
    }
    try {
        await runExclusiveConversationPdfExport(host, conversation.id, async () => {
            const title = resolveConversationExportTitle(conversation);
            const exportedAt = new Date();
            if (shouldAbortConversationExportForRunningState(host, request)) {
                return;
            }
            await startAndDownloadConversationPdfExport(host, conversation, title, exportedAt, resolveConversationExportModel(conversation, request));
            notifyExportResult(host, true);
        });
    } catch (error) {
        await exportConversationJsonAfterPdfFailure(host, request, resolveConversationPdfExportError(ensureError(error)));
    }
};

const exportConversation = (host: MessageSendingHost, conversationId: string | null): void => {
    if (isHeaderExportLoading(host, conversationId)) {
        return;
    }
    const request = createConversationExportRequest(host, conversationId);
    if (shouldAbortConversationExportForRunningState(host, request)) {
        return;
    }
    const loadingState = beginHeaderExportLoading(host, conversationId);
    if (host.model.getParameters().conversationPdfExportEnabled === true) {
        void host.platform
            .runWithBoundary('chat:exportConversationPdf', () => exportConversationPdf(host, request))
            .finally(() => endHeaderExportLoading(host, loadingState))
            .catch((error) => host.platform.handleError(error, i18n.t('chat.export.pdf.title'), { notify: true }));
        return;
    }
    void host.platform
        .runWithBoundary('chat:exportConversationJson', () => exportConversationJson(host, request))
        .finally(() => endHeaderExportLoading(host, loadingState))
        .catch((error) => host.platform.handleError(error, i18n.t('chat.export.pdf.title'), { notify: true }));
};

export { exportConversation, resolveConversationPdfExportError };
