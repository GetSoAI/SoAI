/* SoAI - Chat feature open tool call output modal [frontend/assets/ts/features/chat/modals/toolcalloutputmodal/openToolCallOutputModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { decodeToolCallLiveEventsPage, serializeToolCallLiveEventsPageRequest, serializeToolCallSnapshotRequest, type ToolCallLiveEventsPage } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';
import { escapeAttribute, escapeHtml } from '@core/security/textSanitizer.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CopyActionDependencies } from '@features/chat/message/messageCopyNotifications.ts';
import { ChatToolCallOutputModal } from '@features/chat/modals/toolcalloutputmodal/service.ts';
import { requireConversationId, requireToolCallId } from '@features/chat/validation/ids.ts';
import { requireAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';

interface OpenToolCallOutputModalArguments {
    conversationId: JsonValue | null | undefined;
    callId: JsonValue | null | undefined;
    assistantTurnTimestamp: JsonValue | null | undefined;
    modelVariantIndex: JsonValue | null | undefined;
}

const openChatToolCallOutputModal = async (host: CopyActionDependencies, inputArguments: OpenToolCallOutputModalArguments): Promise<void> => {
    const normalizedConversationId = requireConversationId(inputArguments.conversationId, 'Conversation');
    const normalizedCallId = requireToolCallId(inputArguments.callId, 'Tool call');
    const assistantIdentity = requireAssistantVariantIdentity({
        assistantTurnTimestamp: inputArguments.assistantTurnTimestamp,
        modelVariantIndex: inputArguments.modelVariantIndex,
        context: 'Tool call output'
    });
    const loadLiveEventsPage = async (beforeLiveSequence: number | null): Promise<ToolCallLiveEventsPage> => {
        const requestPayload = serializeToolCallLiveEventsPageRequest({
            conversationId: normalizedConversationId,
            callId: normalizedCallId,
            assistantTurnAtMs: assistantIdentity.assistantTurnTimestamp,
            modelVariantIndex: assistantIdentity.modelVariantIndex,
            limit: 50,
            beforeLiveSequence: beforeLiveSequence ?? undefined
        });
        const liveHistory = await requestWebSocketSnapshotPayload('webui.chat.tool_call_live_events.page', requestPayload);
        return decodeToolCallLiveEventsPage(liveHistory);
    };

    const modal = new ChatToolCallOutputModal({
        escapeHtml: (value) => escapeHtml(value),
        escapeAttribute: (value) => escapeAttribute(value),
        runWithBoundary: (name, functionValue) => host.runWithBoundary(name, functionValue),
        hasClipboardSupport: () => host.hasClipboardSupport(),
        copyToClipboard: (text, options) => host.copyToClipboard(text, options),
        showNotification: (message, type) => host.showNotification(message, type),
        loadMoreLiveEvents: async (beforeLiveSequence) => {
            return loadLiveEventsPage(beforeLiveSequence);
        }
    });

    modal.showLoading();
    try {
        await host.runWithBoundary('chat:toolCallOutputModal', async () => {
            const payload = await requestWebSocketSnapshotPayload(
                'webui.chat.tool_calls.by_call_id',
                serializeToolCallSnapshotRequest({
                    conversationId: normalizedConversationId,
                    callId: normalizedCallId,
                    assistantTurnAtMs: assistantIdentity.assistantTurnTimestamp,
                    modelVariantIndex: assistantIdentity.modelVariantIndex
                })
            );
            const toolCall = requireRecord(payload, i18n.t('chat.toolCallOutputModal.invalidSnapshot'));
            toolCall['liveEventsPage'] = await loadLiveEventsPage(null);
            modal.showToolCall(toolCall);
        });
    } catch (error) {
        const normalizedError = ensureError(error);
        errorHandler.error('ChatPage', 'Failed to load tool call output snapshot', normalizedError);
        modal.showError(i18n.t('chat.toolCallOutputModal.failed'));
    }
};

export { openChatToolCallOutputModal };
