/* SoAI - Chat stream status-preview event validation [frontend/assets/ts/core/realtime/eventcontracts/chatStreamStatusPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonRecord, JsonValue } from '@core/types/jsonValues.ts';
import { isBoolean, isNumber, isPlainObject, isPositiveInteger, isString } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';
import type { ChatStreamTranslationKey } from '@core/i18n/translationkeys/chat/stream.generated.ts';
import { isEpochMsValue } from '@core/time/epochMs.ts';
import { toTrimmedString } from '@core/normalize.ts';

type ChatStreamPreviewTranslationKey = Extract<ChatStreamTranslationKey, `chat.stream.preview.${string}`>;

type ChatStreamStatusPreviewEventEnvelope = {
    type: string;
    userId: number;
    convId: string;
    requestId: string;
    assistantAtMs: number;
    previewKey: ChatStreamPreviewTranslationKey;
    previewArguments?: JsonRecord | null;
    generatedAtMs: number;
    previewCooldownMs: number;
    trigger: string;
};

const isChatStreamPreviewTranslationKey = (value: JsonValue): value is ChatStreamPreviewTranslationKey => {
    if (!isString(value)) {
        return false;
    }
    const normalized = value.trim();
    return normalized === value && normalized.startsWith('chat.stream.preview.');
};

const isPreviewArguments = (value: JsonValue): value is JsonRecord => {
    if (!isPlainObject(value)) {
        return false;
    }
    const record: JsonRecord = value;
    for (const key of Object.keys(record)) {
        if (!key.trim()) {
            return false;
        }
        const entry = record[key];
        if (!(isString(entry) || isNumber(entry) || isBoolean(entry))) {
            return false;
        }
    }
    return true;
};

const parseChatStreamStatusPreviewEventEnvelope = (value: JsonValue): ChatStreamStatusPreviewEventEnvelope | null => {
    if (!isPlainObject(value)) {
        return null;
    }
    if (value['type'] !== WEBSOCKET_EVENT_TYPES.CHAT_STREAM_STATUS_PREVIEW) {
        return null;
    }
    const convId = toTrimmedString(value['conv_id']);
    if (!convId) {
        return null;
    }
    const requestId = value['request_id'];
    if (!isString(requestId) || !requestId.trim()) {
        return null;
    }
    const assistantTimestamp = value['assistant_at_ms'];
    const generatedAtMs = value['generated_at_ms'];
    const previewCooldownMs = value['preview_cooldown_ms'];
    const previewKey = value['preview_key'];
    const previewArguments = value['preview_args'];
    const hasValidAssistantTimestamp = isEpochMsValue(assistantTimestamp);
    const hasValidGeneratedAt = isEpochMsValue(generatedAtMs);
    const hasValidPreviewCooldown = isPositiveInteger(previewCooldownMs);
    const hasValidPreviewKey = previewKey !== undefined && isChatStreamPreviewTranslationKey(previewKey);
    const hasValidPreviewArguments = previewArguments === null || previewArguments === undefined || isPreviewArguments(previewArguments);
    const trigger = value['trigger'];
    const userId = value['user_id'];
    if (!isPositiveInteger(userId) || !hasValidAssistantTimestamp || !hasValidGeneratedAt || !hasValidPreviewCooldown || !hasValidPreviewKey || !hasValidPreviewArguments || !isString(trigger) || !trigger.trim()) {
        return null;
    }
    return {
        type: WEBSOCKET_EVENT_TYPES.CHAT_STREAM_STATUS_PREVIEW,
        userId,
        convId,
        requestId: requestId.trim(),
        assistantAtMs: assistantTimestamp,
        previewKey,
        previewArguments: previewArguments ?? null,
        generatedAtMs,
        previewCooldownMs,
        trigger: trigger.trim()
    };
};

export type { ChatStreamStatusPreviewEventEnvelope };
export { parseChatStreamStatusPreviewEventEnvelope };
