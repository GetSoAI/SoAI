/* SoAI - Chat feature stream message updates [frontend/assets/ts/features/chat/chatstreamservice/streamMessageUpdates.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import { calculateGenerationSpeed } from '@features/chat/conversationFormatting.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';
import { isContextCompactionBoundaryMessage } from '@features/chat/message/contextcompaction/detection.ts';

const resolveAssistantGenerationLatencyMs = (message: ChatMessage, nowMs: number = serverEpochMs()): number | null => {
    if (!hasTerminalAssistantState(message) || isContextCompactionBoundaryMessage(message)) return null;
    if (isNumber(message.generationLatencyMs) && Number.isFinite(message.generationLatencyMs) && message.generationLatencyMs >= 0) return Math.floor(message.generationLatencyMs);
    const startedAtMs = message.assistantTurnAtMs;
    return isNumber(startedAtMs) && Number.isFinite(startedAtMs) && Number.isFinite(nowMs) ? Math.max(0, Math.floor(nowMs - startedAtMs)) : null;
};

const applyGenerationMetrics = (session: ChatStreamSession, terminalAtMs: number): void => {
    const generationLatencyMs = resolveAssistantGenerationLatencyMs(session.assistantMessage, terminalAtMs);
    if (generationLatencyMs === null) {
        return;
    }
    if (!isNumber(session.assistantMessage.generationLatencyMs) || !Number.isFinite(session.assistantMessage.generationLatencyMs) || session.assistantMessage.generationLatencyMs < 0) session.assistantMessage.generationLatencyMs = generationLatencyMs;
    const generationSpeed = calculateGenerationSpeed(session.assistantMessage.completionTokens, generationLatencyMs);
    if (generationSpeed !== null && (!isNumber(session.assistantMessage.generationSpeedTokensPerSec) || !Number.isFinite(session.assistantMessage.generationSpeedTokensPerSec) || session.assistantMessage.generationSpeedTokensPerSec < 0)) {
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
