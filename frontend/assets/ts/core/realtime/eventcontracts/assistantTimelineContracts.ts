/* SoAI - Frontend assistant timeline wire contracts [frontend/assets/ts/core/realtime/eventcontracts/assistantTimelineContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseTokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';
import { decodeAssistantActivity } from '@core/realtime/eventcontracts/assistantActivityContracts.ts';
import { decodeAssistantThinkingPhase } from '@core/realtime/eventcontracts/assistantThinkingContracts.ts';
import { decodeAssistantTimelineTool } from '@core/realtime/eventcontracts/assistantToolContracts.ts';
import type { AssistantCompletedUsage, AssistantEventTimelineItem, AssistantTimelinePayload } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isNonNegativeInteger, isPositiveInteger, isString } from '@core/typeGuards.ts';

const decodeCompletedUsage = (value: JsonValue | undefined): AssistantCompletedUsage | null | undefined => {
    if (value === undefined || value === null) return value;
    if (!isJsonObject(value)) return undefined;
    if (Object.keys(value).length === 0) return null;
    const promptTokens = value['prompt_tokens'];
    const completionTokens = value['completion_tokens'];
    const totalTokens = value['total_tokens'];
    const usageSource = value['usage_source'];
    if (!isNonNegativeInteger(promptTokens) || !isNonNegativeInteger(completionTokens) || !isNonNegativeInteger(totalTokens) || totalTokens !== promptTokens + completionTokens || !isString(usageSource) || !usageSource.trim()) return undefined;
    return { promptTokens, completionTokens, totalTokens, usageSource: usageSource.trim() };
};

const decodeTimelineIdentity = (record: JsonObject): AssistantTimelinePayload | null => {
    const assistantAtMs = record['assistant_at_ms'];
    const assistantTurnAtMs = record['assistant_turn_at_ms'];
    const assistantRevision = record['assistant_revision'];
    const modelVariantIndex = record['model_variant_index'];
    if (!isPositiveInteger(assistantAtMs) || !isPositiveInteger(assistantTurnAtMs) || !isPositiveInteger(assistantRevision) || !isNonNegativeInteger(modelVariantIndex)) return null;
    return { assistantAtMs, assistantTurnAtMs, assistantRevision, modelVariantIndex };
};

const decodeActivityPayload = (identity: AssistantTimelinePayload, record: JsonObject, wireKey: 'loading_activity' | 'processing_activity' | 'wait_for_user_activity'): AssistantTimelinePayload | null => {
    const activity = decodeAssistantActivity(record[wireKey]);
    if (activity === null) return null;
    if (wireKey === 'loading_activity') return { ...identity, loadingActivity: activity };
    if (wireKey === 'processing_activity') return { ...identity, processingActivity: activity };
    return { ...identity, waitForUserActivity: activity };
};

const decodeAssistantTimelinePayload = (eventType: string, value: JsonValue | null | undefined): AssistantTimelinePayload | null => {
    if (!isJsonObject(value)) return null;
    const identity = decodeTimelineIdentity(value);
    if (identity === null) return null;
    const usagePreviewValue = value['usage_preview'];
    if (usagePreviewValue !== undefined && usagePreviewValue !== null) {
        const usagePreview = parseTokenUsageSnapshot(usagePreviewValue);
        if (usagePreview === null) return null;
        identity.usagePreview = usagePreview;
    }
    if (eventType === 'assistant_text_delta') {
        const delta = value['delta'];
        return isString(delta) && delta.length > 0 ? { ...identity, delta } : null;
    }
    if (eventType === 'assistant_image') {
        const image = value['image'];
        const url = isJsonObject(image) ? image['url'] : null;
        return isString(url) && url.trim() ? { ...identity, image: { url: url.trim() } } : null;
    }
    if (eventType === 'tool_call_created' || eventType === 'tool_call_started' || eventType === 'tool_call_completed') {
        const tool = decodeAssistantTimelineTool(value['tool']);
        return tool === null ? null : { ...identity, tool };
    }
    if (eventType === 'thinking_phase') {
        const thinkingPhase = decodeAssistantThinkingPhase(value['thinking_phase']);
        return thinkingPhase === null ? null : { ...identity, thinkingPhase };
    }
    if (eventType === 'loading_activity' || eventType === 'processing_activity' || eventType === 'wait_for_user_activity') return decodeActivityPayload(identity, value, eventType);
    if (eventType === 'completed') {
        const finishReason = value['finish_reason'];
        const usage = decodeCompletedUsage(value['usage']);
        if (!isString(finishReason) || !finishReason.trim() || usage === undefined) return null;
        return { ...identity, finishReason: finishReason.trim(), usage };
    }
    if (eventType === 'cancelled') {
        const reason = value['reason'];
        const code = value['code'];
        if (!isString(reason) || !reason.trim() || !isString(code) || !code.trim()) return null;
        return { ...identity, reason: reason.trim(), code: code.trim() };
    }
    if (eventType === 'error') {
        const message = value['message'];
        const code = value['code'];
        const referenceId = value['reference_id'];
        if (!isString(message) || !message.trim() || !isString(code) || !code.trim() || !isString(referenceId) || !referenceId.trim()) return null;
        return { ...identity, message: message.trim(), code: code.trim(), referenceId: referenceId.trim(), ...(value['preview_contract'] !== undefined ? { previewContract: value['preview_contract'] } : {}) };
    }
    return null;
};

const parseAssistantTimeline = (value: JsonValue | null | undefined): AssistantEventTimelineItem[] | null => {
    if (!Array.isArray(value)) return null;
    const timeline: AssistantEventTimelineItem[] = [];
    for (let index = 0; index < value.length; index += 1) {
        const entry = value[index];
        if (!isJsonObject(entry)) return null;
        const sequence = entry['sequence'];
        const assistantRevision = entry['assistant_revision'];
        const eventType = entry['event_type'];
        if (!isNonNegativeInteger(sequence) || sequence !== index) return null;
        if (!isPositiveInteger(assistantRevision) || assistantRevision !== sequence + 1) return null;
        if (!isString(eventType) || !eventType.trim() || eventType !== eventType.trim()) return null;
        const payload = decodeAssistantTimelinePayload(eventType, entry['payload']);
        if (payload === null || payload.assistantRevision !== assistantRevision) return null;
        timeline.push({ sequence, assistantRevision, eventType, payload });
    }
    return timeline;
};

const parseAssistantTimelineProjection = (value: JsonValue | null | undefined): AssistantEventTimelineItem[] | null => {
    if (!Array.isArray(value)) return null;
    const timeline: AssistantEventTimelineItem[] = [];
    let expectedSourceSequenceStart = 0;
    let previousEventType: string | null = null;
    for (const entry of value) {
        if (!isJsonObject(entry)) return null;
        const sourceSequenceStart = entry['source_sequence_start'];
        const sequence = entry['sequence'];
        const assistantRevision = entry['assistant_revision'];
        const eventType = entry['event_type'];
        if (!isNonNegativeInteger(sourceSequenceStart) || sourceSequenceStart !== expectedSourceSequenceStart) return null;
        if (!isNonNegativeInteger(sequence) || sequence < sourceSequenceStart) return null;
        if (!isPositiveInteger(assistantRevision) || assistantRevision !== sequence + 1) return null;
        if (!isString(eventType) || !eventType.trim() || eventType !== eventType.trim()) return null;
        if (sourceSequenceStart !== sequence && eventType !== 'assistant_text_delta') return null;
        if (eventType === 'assistant_text_delta' && previousEventType === eventType) return null;
        const payload = decodeAssistantTimelinePayload(eventType, entry['payload']);
        if (payload === null || payload.assistantRevision !== assistantRevision) return null;
        timeline.push({ sourceSequenceStart, sequence, assistantRevision, eventType, payload });
        expectedSourceSequenceStart = sequence + 1;
        previousEventType = eventType;
    }
    return timeline;
};

const decodeAssistantTimeline = (value: JsonValue | null | undefined): AssistantEventTimelineItem[] => {
    const timeline = parseAssistantTimeline(value);
    if (timeline === null) throw new TypeError('Assistant event timeline is invalid');
    return timeline;
};

const decodeAssistantTimelineProjection = (value: JsonValue | null | undefined): AssistantEventTimelineItem[] => {
    const timeline = parseAssistantTimelineProjection(value);
    if (timeline === null) throw new TypeError('Assistant event timeline projection is invalid');
    return timeline;
};

export { decodeAssistantTimeline, decodeAssistantTimelinePayload, decodeAssistantTimelineProjection, parseAssistantTimeline, parseAssistantTimelineProjection };
