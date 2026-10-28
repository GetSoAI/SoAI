/* SoAI - Chat feature assistant output notice resolution [frontend/assets/ts/features/chat/message/assistantOutputNotice.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_STREAM_STEER_INTERRUPTED_CODE, CHAT_STREAM_USER_STOPPED_CODE } from '@core/chat/protocols.ts';
import { i18n } from '@core/i18n/index.ts';
import { isString } from '@core/typeGuards.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import { timelineHasVisibleAssistantTextDelta } from '@features/chat/assistanteventtimeline/timelineTextDeltas.ts';
import type { ChatContent, ChatContentSegment, ChatMessage } from '@features/chat/ChatTypes.ts';
import { resolveAssistantTerminalState, resolveDurableAssistantTerminalState } from '@features/chat/message/assistantTerminalState.ts';

type AssistantOutputNoticeType = 'token_limit' | 'token_limit_reasoning' | 'reasoning_only';

interface AssistantOutputShape {
    hasText: boolean;
    hasReasoning: boolean;
    hasToolCalls: boolean;
}

const TOKEN_LIMIT_FINISH_REASONS: ReadonlySet<string> = new Set(['length', 'max_tokens', 'max_output_tokens']);

const listContentParts = (content: ChatContent | undefined): ChatContentSegment[] => {
    if (content === undefined || content === null) {
        return [];
    }
    return Array.isArray(content) ? content : [content];
};

const resolveAssistantOutputShape = (message: ChatMessage): AssistantOutputShape => {
    const shape: AssistantOutputShape = {
        hasText: timelineHasVisibleAssistantTextDelta(message.assistantEventTimeline),
        hasReasoning: false,
        hasToolCalls: (message.toolCalls?.length ?? 0) > 0
    };
    for (const part of listContentParts(message.content)) {
        if (isString(part)) {
            shape.hasText ||= part.trim().length > 0;
            continue;
        }
        const text = 'text' in part && isString(part.text) ? part.text.trim() : '';
        if (part.type === 'text') {
            shape.hasText ||= text.length > 0;
        } else if (part.type === 'thinking') {
            shape.hasReasoning ||= text.length > 0;
        } else if (part.type === 'tool_call') {
            shape.hasToolCalls = true;
        }
    }
    return shape;
};

const resolveAssistantOutputNoticeType = (message: ChatMessage): AssistantOutputNoticeType | null => {
    if (message.role !== 'assistant' || resolveAssistantTerminalState(message) !== 'complete') {
        return null;
    }
    const shape = resolveAssistantOutputShape(message);
    const finishReason = optionalTrimmedString(message.finishReason)?.toLowerCase() ?? '';
    if (TOKEN_LIMIT_FINISH_REASONS.has(finishReason)) {
        return shape.hasText || !shape.hasReasoning ? 'token_limit' : 'token_limit_reasoning';
    }
    if (shape.hasReasoning && !shape.hasText && !shape.hasToolCalls) {
        return 'reasoning_only';
    }
    return null;
};

const resolveAssistantOutputNoticeText = (message: ChatMessage): string | null => {
    const cancellationReason = resolveAssistantCancellationReason(message);
    if (cancellationReason !== null) {
        return cancellationReason;
    }
    switch (resolveAssistantOutputNoticeType(message)) {
        case 'token_limit':
            return i18n.t('chat.message.outputNotices.tokenLimit');
        case 'token_limit_reasoning':
            return i18n.t('chat.message.outputNotices.tokenLimitReasoning');
        case 'reasoning_only':
            return i18n.t('chat.message.outputNotices.reasoningOnly');
        case null:
            return null;
    }
};

const resolveCancellationCodeNotice = (code: string | null | undefined): string | null => {
    switch (code) {
        case CHAT_STREAM_STEER_INTERRUPTED_CODE:
            return i18n.t('chat.message.outputNotices.steered');
        case CHAT_STREAM_USER_STOPPED_CODE:
            return i18n.t('chat.message.outputNotices.stopped');
        default:
            return null;
    }
};

const resolveAssistantCancellationReason = (message: ChatMessage): string | null => {
    if (message.role !== 'assistant' || resolveDurableAssistantTerminalState(message) !== 'cancelled') {
        return null;
    }
    const timeline = message.assistantEventTimeline ?? [];
    for (let index = timeline.length - 1; index >= 0; index -= 1) {
        const event = timeline[index];
        if (event?.eventType === 'cancelled') {
            return resolveCancellationCodeNotice(event.payload.code) ?? optionalTrimmedString(event.payload.reason);
        }
    }
    return null;
};

export { resolveAssistantCancellationReason, resolveAssistantOutputNoticeText, resolveAssistantOutputNoticeType, resolveCancellationCodeNotice };
export type { AssistantOutputNoticeType };
