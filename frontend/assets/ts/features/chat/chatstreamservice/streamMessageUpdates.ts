/* SoAI - Chat feature stream message updates [frontend/assets/ts/features/chat/chatstreamservice/streamMessageUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { calculateGenerationSpeed } from '@features/chat/conversationFormatting.ts';
import { resolveAssistantSettledResponseDisplayDurationMs } from '@features/chat/message/assistantResponseDuration.ts';

const resolveAssistantGenerationLatencyMs = (message: ChatMessage, nowMs: number = serverEpochMs()): number | null => {
    const durationMs = resolveAssistantSettledResponseDisplayDurationMs(message, nowMs);
    if (!isNumber(durationMs) || !Number.isFinite(durationMs) || durationMs < 0) {
        return null;
    }
    return Math.floor(durationMs);
};

const applyGenerationMetrics = (session: ChatStreamSession): void => {
    const generationLatencyMs = resolveAssistantGenerationLatencyMs(session.assistantMessage);
    if (generationLatencyMs === null) {
        return;
    }
    session.assistantMessage.generationLatencyMs = generationLatencyMs;
    const generationSpeed = calculateGenerationSpeed(session.assistantMessage.completionTokens, generationLatencyMs);
    if (generationSpeed !== null) {
        session.assistantMessage.generationSpeedTokensPerSec = generationSpeed;
    }
};

const appendAssistantTextDelta = (message: ChatMessage, delta: string): void => {
    if (!delta) {
        return;
    }
    const existing = message.content;
    if (isString(existing)) {
        message.content = existing + delta;
        return;
    }
    if (isArray(existing)) {
        const contentParts = [...existing];
        const lastIndex = existing.length - 1;
        const lastPart = lastIndex >= 0 ? existing[lastIndex] : null;
        if (isString(lastPart)) {
            contentParts[lastIndex] = lastPart + delta;
            message.content = contentParts;
            return;
        }
        if (isPlainObject(lastPart) && lastPart['type'] === 'text' && isString(lastPart['text'])) {
            const value = 'value' in lastPart && isString(lastPart.value) ? lastPart.value + delta : lastPart['text'] + delta;
            contentParts[lastIndex] = { type: 'text', text: lastPart['text'] + delta, value };
            message.content = contentParts;
            return;
        }
        message.content = [...contentParts, { type: 'text', text: delta, value: delta }];
        return;
    }
    if (isPlainObject(existing)) {
        if (existing['type'] === 'text' && isString(existing['text'])) {
            const value = 'value' in existing && isString(existing.value) ? existing.value + delta : existing['text'] + delta;
            message.content = { type: 'text', text: existing['text'] + delta, value };
            return;
        }
        message.content = [existing, { type: 'text', text: delta, value: delta }];
        return;
    }
    message.content = delta;
};

export { applyGenerationMetrics, appendAssistantTextDelta, resolveAssistantGenerationLatencyMs };
