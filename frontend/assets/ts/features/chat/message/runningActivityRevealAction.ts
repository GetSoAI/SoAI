/* SoAI - Chat running activity reveal action [frontend/assets/ts/features/chat/message/runningActivityRevealAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requestWebSocketSnapshotPayload } from '@core/websocketclient/snapshotPayload.ts';
import { serializeToolCallSnapshotRequest } from '@core/api/contracts/chatRealtimeSnapshotContracts.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { mapAssistantTimelineToolPayload } from '@features/chat/assistanteventtimeline/toolPayloadMapper.ts';
import type { ChatMessageActionData, ChatMessageActionsDependencies } from '@features/chat/message/actionDeps.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { toggleLoadingActivityItem } from '@features/chat/message/loadingActivityToggle.ts';
import { COLLAPSED_LOADING_CONTENT_SELECTOR } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { setRunningActivityRevealPending } from '@features/chat/message/messageRunningActivitySummaryMarkup.ts';
import { buildAssistantVariantMessageDomId } from '@features/chat/message/messageDomIds.ts';
import type { ConversationRunningActivitySnapshot, RunningActivityTargetSnapshot } from '@features/chat/storage/storageModels.ts';
import { upsertToolCallProjection } from '@features/chat/toolactivity/toolProjectionMutation.ts';

const resolveActivityElementByCallId = (container: HTMLElement, callId: string): HTMLElement | null => {
    const element = dom.resolve(`.inline-activity[data-call-id="${CSS.escape(callId)}"]`, container);
    return element instanceof HTMLElement ? element : null;
};

const revealTargetFromContainer = (dependencies: ChatMessageActionsDependencies, container: HTMLElement, callId: string, ancestorCallIds: readonly string[]): boolean => {
    const targetElement = resolveActivityElementByCallId(container, callId);
    if (targetElement !== null) {
        dependencies.presentation.revealActivityElement(targetElement);
        return true;
    }
    for (const ancestorCallId of ancestorCallIds) {
        const ancestorElement = resolveActivityElementByCallId(container, ancestorCallId);
        if (ancestorElement !== null) {
            dependencies.presentation.revealActivityElement(ancestorElement);
            return true;
        }
    }
    return false;
};

const revealTargetInMessage = (dependencies: ChatMessageActionsDependencies, messageId: string, target: RunningActivityTargetSnapshot): boolean => {
    const renderedContainer = dependencies.presentation.resolveMessageContainer(messageId);
    if (renderedContainer === null) {
        return false;
    }
    if (dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, renderedContainer) !== null) {
        toggleLoadingActivityItem(dependencies, messageId);
    }
    const container = dependencies.presentation.resolveMessageContainer(messageId);
    return container !== null && revealTargetFromContainer(dependencies, container, target.callId, target.ancestorCallIds);
};

const resolveTargetMessage = (conversation: NonNullable<ReturnType<ChatMessageActionsDependencies['session']['getCurrentConversation']>>, assistantTurnAtMs: number, modelVariantIndex: number): ChatMessage | null => {
    for (const candidate of conversation.messages) {
        if (!isChatMessage(candidate) || candidate.role !== 'assistant') {
            continue;
        }
        if (candidate.assistantTurnAtMs === assistantTurnAtMs && candidate.modelVariantIndex === modelVariantIndex) {
            return candidate;
        }
    }
    return null;
};

const hydrateTargetProjection = async (conversationId: string, message: ChatMessage, callId: string): Promise<boolean> => {
    const assistantTurnAtMs = message.assistantTurnAtMs;
    const modelVariantIndex = message.modelVariantIndex;
    if (typeof assistantTurnAtMs !== 'number' || typeof modelVariantIndex !== 'number') {
        return false;
    }
    const snapshot = await requestWebSocketSnapshotPayload(
        'webui.chat.tool_calls.by_call_id',
        serializeToolCallSnapshotRequest({
            conversationId,
            callId: callId,
            assistantTurnAtMs: assistantTurnAtMs,
            modelVariantIndex: modelVariantIndex
        })
    );
    const projection = mapAssistantTimelineToolPayload(snapshot);
    if (projection === null || projection.callId !== callId) {
        return false;
    }
    upsertToolCallProjection(message, projection);
    return true;
};

const resolveRevealTarget = (snapshot: ConversationRunningActivitySnapshot, message: ChatMessage): RunningActivityTargetSnapshot | null => {
    const terminal = hasTerminalAssistantState(message);
    const activityCount = terminal ? snapshot.backgroundActivityCount : snapshot.activityCount;
    const subagentCount = terminal ? snapshot.backgroundSubagentCount : snapshot.subagentCount;
    if (activityCount <= 0 && subagentCount <= 0) {
        return null;
    }
    return terminal ? snapshot.backgroundTarget : snapshot.target;
};

const revealBackendRunningActivityTarget = async (dependencies: ChatMessageActionsDependencies, conversationId: string, message: ChatMessage): Promise<void> => {
    await dependencies.runtime.refreshRunningActivitySnapshot(conversationId);
    if (dependencies.session.getCurrentConversation()?.id !== conversationId) {
        return;
    }
    const snapshot = dependencies.session.getCurrentRunningActivitySnapshot();
    if (snapshot === null) {
        await dependencies.runtime.renderCurrentConversation();
        return;
    }
    const target = resolveRevealTarget(snapshot, message);
    if (target === null) {
        await dependencies.runtime.renderCurrentConversation();
        return;
    }
    const targetMessageId = buildAssistantVariantMessageDomId(target.assistantTurnAtMs, target.modelVariantIndex);
    if (revealTargetInMessage(dependencies, targetMessageId, target)) {
        return;
    }
    await dependencies.runtime.loadConversationMessages(conversationId, {
        direction: 'around',
        anchor: target.messageCursor,
        force: true
    });
    const loadedConversation = dependencies.session.getCurrentConversation();
    if (loadedConversation?.id !== conversationId) {
        return;
    }
    await dependencies.runtime.renderCurrentConversation();
    if (revealTargetInMessage(dependencies, targetMessageId, target)) {
        return;
    }
    const targetMessage = resolveTargetMessage(loadedConversation, target.assistantTurnAtMs, target.modelVariantIndex);
    if (targetMessage !== null && (await hydrateTargetProjection(conversationId, targetMessage, target.callId))) {
        if (dependencies.session.getCurrentConversation()?.id !== conversationId) {
            return;
        }
        dependencies.presentation.invalidateMessageCache(targetMessage);
        await dependencies.runtime.renderCurrentConversation();
        if (revealTargetInMessage(dependencies, targetMessageId, target)) {
            return;
        }
    }
};

const revealRunningActivity = async (dependencies: ChatMessageActionsDependencies, revealOperationByConversationId: Map<string, Promise<void>>, _messageId: string, message: ChatMessage, data: ChatMessageActionData | undefined): Promise<void> => {
    setRunningActivityRevealPending(data?.actionElement, true);
    const conversation = dependencies.session.getCurrentConversation();
    if (conversation === null || typeof conversation.id !== 'string' || !conversation.id.trim()) {
        setRunningActivityRevealPending(data?.actionElement, false);
        return;
    }
    const conversationId = conversation.id;
    const existingOperation = revealOperationByConversationId.get(conversationId);
    if (existingOperation !== undefined) {
        try {
            await existingOperation;
        } finally {
            setRunningActivityRevealPending(data?.actionElement, false);
        }
        return;
    }
    const operation = revealBackendRunningActivityTarget(dependencies, conversationId, message);
    revealOperationByConversationId.set(conversationId, operation);
    try {
        await operation;
    } finally {
        setRunningActivityRevealPending(data?.actionElement, false);
        if (revealOperationByConversationId.get(conversationId) === operation) {
            revealOperationByConversationId.delete(conversationId);
        }
    }
};

export { revealRunningActivity };
