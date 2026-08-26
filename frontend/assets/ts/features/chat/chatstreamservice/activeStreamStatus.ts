/* SoAI - Active chat stream status snapshot parsing [frontend/assets/ts/features/chat/chatstreamservice/activeStreamStatus.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationStreamStatusResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { isEpochMsValue } from '@core/time/epochMs.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import type { JsonObject, JsonRecord } from '@core/types/jsonValues.ts';
import { isBoolean, isNumber, isPositiveInteger, isString } from '@core/typeGuards.ts';
import { resolveAssistantMessageIdentity } from '@core/chat/assistantIdentity.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type ActiveChatStreamIdentity = {
    requestId: string;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

type ChatStreamLifecycle = 'inactive' | 'streaming' | 'terminalizing';

type ChatStreamAdmissionStatus = {
    streamLifecycle: ChatStreamLifecycle;
    canAcceptConversationInput: boolean;
    canStartNextPrompt: boolean;
    canAcceptSteerPrompt: boolean;
    activeToolCallCount: number;
};

type ActiveChatStreamStatus = ActiveChatStreamIdentity & {
    active: true;
    conversationId: string;
    admission: ChatStreamAdmissionStatus;
    modelId: string | null;
    previewKey: string | null;
    previewArguments: JsonRecord | null;
    previewGeneratedAtMs: number | null;
    previewCooldownMs: number | null;
    previewTrigger: string | null;
};

type InactiveChatStreamStatus = {
    active: false;
    conversationId: string;
    startAdmission: 'inactive' | 'busy' | 'unknown';
    admission: ChatStreamAdmissionStatus;
};

type ChatStreamStatusSnapshot = ActiveChatStreamStatus | InactiveChatStreamStatus;

type OptionalPreviewArgumentsRead = {
    valid: boolean;
    value: JsonRecord | null;
};

const identitiesMatchActiveStatus = (left: ActiveChatStreamStatus, right: ActiveChatStreamStatus): boolean => {
    return left.conversationId === right.conversationId && left.requestId === right.requestId && left.assistantTimestamp === right.assistantTimestamp && left.assistantTurnTimestamp === right.assistantTurnTimestamp && left.modelVariantIndex === right.modelVariantIndex;
};

const mapAdmissionStatus = (value: ConversationStreamStatusResponse): ChatStreamAdmissionStatus => ({
    streamLifecycle: value.streamLifecycle,
    canAcceptConversationInput: value.canAcceptConversationInput,
    canStartNextPrompt: value.canStartNextPrompt,
    canAcceptSteerPrompt: value.canAcceptSteerPrompt,
    activeToolCallCount: value.activeToolCallCount
});

const readOptionalPreviewArguments = (value: JsonObject | undefined): OptionalPreviewArgumentsRead => {
    if (value === undefined) {
        return { valid: true, value: null };
    }
    const result: JsonRecord = {};
    for (const key of Object.keys(value)) {
        if (!key.trim()) {
            return { valid: false, value: null };
        }
        const entry = value[key];
        if (!(isString(entry) || isNumber(entry) || isBoolean(entry))) {
            return { valid: false, value: null };
        }
        result[key] = entry;
    }
    return { valid: true, value: result };
};

const mapChatStreamStatusSnapshot = (value: ConversationStreamStatusResponse): ChatStreamStatusSnapshot | null => {
    const conversationId = normalizeConversationId(value.conversationId);
    if (!conversationId) {
        return null;
    }
    const admission = mapAdmissionStatus(value);
    if (value.active === false) {
        return { active: false, conversationId, startAdmission: value.startAdmission, admission };
    }
    const requestIdValue = value.requestId;
    const identity = resolveAssistantMessageIdentity({
        assistantTimestamp: value.assistantAtMs,
        assistantTurnTimestamp: value.assistantTurnAtMs,
        modelVariantIndex: value.modelVariantIndex
    });
    if (!isString(requestIdValue) || !requestIdValue.trim() || identity === null) {
        return null;
    }
    const modelId = toTrimmedStringOrNull(value.modelId);
    if (value.modelId !== undefined && modelId === null) {
        return null;
    }
    const previewKey = toTrimmedStringOrNull(value.previewKey);
    if (value.previewKey !== undefined && previewKey === null) {
        return null;
    }
    const previewGeneratedAtMsValue = value.previewGeneratedAtMs;
    const previewGeneratedAtMs = isEpochMsValue(previewGeneratedAtMsValue) ? previewGeneratedAtMsValue : null;
    const previewCooldownMsValue = value.previewCooldownMs;
    const previewCooldownMs = isPositiveInteger(previewCooldownMsValue) ? previewCooldownMsValue : null;
    const previewTriggerValue = value.previewTrigger;
    const previewTrigger = toTrimmedStringOrNull(previewTriggerValue);
    const previewArguments = readOptionalPreviewArguments(value.previewArguments);
    if (!previewArguments.valid) {
        return null;
    }
    if (previewKey === null) {
        if (value.previewArguments !== undefined || value.previewGeneratedAtMs !== undefined || value.previewCooldownMs !== undefined || value.previewTrigger !== undefined) {
            return null;
        }
    } else if (previewGeneratedAtMs === null || previewCooldownMs === null || previewTrigger === null) {
        return null;
    }
    return {
        active: true,
        conversationId,
        admission,
        requestId: requestIdValue.trim(),
        assistantTimestamp: identity.assistantTimestamp,
        assistantTurnTimestamp: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex,
        modelId,
        previewKey,
        previewArguments: previewArguments.value,
        previewGeneratedAtMs,
        previewCooldownMs,
        previewTrigger
    };
};

export { identitiesMatchActiveStatus, mapChatStreamStatusSnapshot };
export type { ActiveChatStreamIdentity, ActiveChatStreamStatus, ChatStreamAdmissionStatus, ChatStreamLifecycle, ChatStreamStatusSnapshot };
