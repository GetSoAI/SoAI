/* SoAI - Conversation export turn model [frontend/assets/ts/features/chat/conversationexport/turnModel.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { AssistantEventTimelineItem, ChatMessage, ConversationContract, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { resolveRenderableConversationEntries, type ComparisonTurnRenderEntry } from '@features/chat/conversation/rendering/conversationEntries.ts';
import { analyzeConversationProjection } from '@features/chat/conversation/rendering/conversationProjectionAnalysis.ts';
import { CONTEXT_COMPACTION_TOOL_LEAF, isContextCompactionBoundaryMessage, isRemovedContextCompactionResult } from '@features/chat/message/contextcompaction/detection.ts';
import type { ChatMessageRenderPresentation } from '@features/chat/message/messageRenderPresentation.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

type ExportCoverTurnKind = 'user' | 'assistant' | 'tool' | 'other';

type ConversationExportMessageTurn = {
    type: 'message';
    kind: ExportCoverTurnKind;
    variantCount: number;
    messages: ChatMessage[];
    previewMessage: ChatMessage | null;
    message: ChatMessage;
    presentation: ChatMessageRenderPresentation;
    isCompactionBoundary: boolean;
};

type ConversationExportComparisonTurn = {
    type: 'comparisonTurn';
    kind: 'assistant';
    variantCount: number;
    messages: ChatMessage[];
    previewMessage: ChatMessage | null;
    entry: ComparisonTurnRenderEntry;
};

type ConversationExportTurn = ConversationExportMessageTurn | ConversationExportComparisonTurn;

const resolveTurnKind = (role: string): ExportCoverTurnKind => {
    if (role === 'user' || role === 'assistant' || role === 'tool') {
        return role;
    }
    return 'other';
};

const isContextCompactionToolName = (value: string): boolean => {
    return isString(value) && normalizeToolLeafName(value) === CONTEXT_COMPACTION_TOOL_LEAF;
};

const isRemovedContextCompactionTimelineEntry = (entry: AssistantEventTimelineItem): boolean => {
    const tool = entry.payload.tool;
    if (tool === undefined || !isContextCompactionToolName(tool.toolName)) {
        return false;
    }
    return isRemovedContextCompactionResult(tool.result);
};

const isRemovedContextCompactionProjection = (item: ToolActivityItem): boolean => {
    return isContextCompactionToolName(item.toolName) && isRemovedContextCompactionResult(item.result);
};

const isRemovedContextCompactionBoundaryMessage = (message: ChatMessage): boolean => {
    const timeline = message.assistantEventTimeline;
    if (Array.isArray(timeline) && timeline.some(isRemovedContextCompactionTimelineEntry)) {
        return true;
    }
    const projections = message.toolCallProjections;
    return Array.isArray(projections) && projections.some(isRemovedContextCompactionProjection);
};

const shouldExportMessage = (message: ChatMessage): boolean => {
    if (!isContextCompactionBoundaryMessage(message)) {
        return true;
    }
    return !isRemovedContextCompactionBoundaryMessage(message);
};

const resolveMessageTurn = (message: ChatMessage, presentation: ChatMessageRenderPresentation): ConversationExportMessageTurn | null => {
    if (!shouldExportMessage(message)) {
        return null;
    }
    const role = isString(message.role) && message.role.trim() ? message.role.trim() : 'user';
    const isCompactionBoundary = isContextCompactionBoundaryMessage(message);
    return {
        type: 'message',
        kind: resolveTurnKind(role),
        variantCount: 1,
        messages: [message],
        previewMessage: message,
        message,
        presentation,
        isCompactionBoundary
    };
};

const resolveComparisonTurn = (entry: ComparisonTurnRenderEntry): ConversationExportComparisonTurn | null => {
    const variantMessages: ChatMessage[] = [];
    for (const variant of entry.variants) {
        if (variant.message !== null && shouldExportMessage(variant.message)) {
            variantMessages.push(variant.message);
        }
    }
    if (variantMessages.length === 0) {
        return null;
    }
    const activeVariant = entry.variants[entry.activeVariantIndex] ?? null;
    const activeMessage = activeVariant?.message ?? null;
    const previewMessage = activeMessage !== null && shouldExportMessage(activeMessage) ? activeMessage : (variantMessages[0] ?? null);
    return {
        type: 'comparisonTurn',
        kind: 'assistant',
        variantCount: entry.variantCount,
        messages: variantMessages,
        previewMessage,
        entry
    };
};

const resolveConversationExportTurns = (conversation: ConversationContract): ConversationExportTurn[] => {
    const analysis = analyzeConversationProjection(conversation, {
        isCurrentStreaming: false,
        activeComparisonRun: null,
        activeStreamIdentity: null,
        isMessagePendingDeletion: () => false
    });
    const entries = resolveRenderableConversationEntries(analysis, {
        activeVariantIndexByAssistantTurnTimestamp: null,
        includeEmptyAssistantPlaceholder: isContextCompactionBoundaryMessage
    });
    const turns: ConversationExportTurn[] = [];
    for (const entry of entries) {
        if (entry.type === 'message') {
            const turn = resolveMessageTurn(entry.message, entry.presentation);
            if (turn !== null) {
                turns.push(turn);
            }
            continue;
        }
        const turn = resolveComparisonTurn(entry);
        if (turn !== null) {
            turns.push(turn);
        }
    }
    return turns;
};

export { resolveConversationExportTurns };
export type { ConversationExportComparisonTurn, ConversationExportMessageTurn, ConversationExportTurn, ExportCoverTurnKind };
