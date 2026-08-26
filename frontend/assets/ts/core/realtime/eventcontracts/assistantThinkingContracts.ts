/* SoAI - Frontend assistant thinking phase contracts [frontend/assets/ts/core/realtime/eventcontracts/assistantThinkingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isBoolean, isNonNegativeInteger, isObject, isString } from '@core/typeGuards.ts';
import type { AssistantThinkingPhase, ThinkingTimelineAnchorType } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

const isThinkingTimelineAnchorType = (value: string): value is ThinkingTimelineAnchorType => value === 'before_call' || value === 'after_call' || value === 'position';

const decodeAssistantThinkingPhase = (value: JsonValue | null | undefined, expectedSequenceIndex: number | null = null): AssistantThinkingPhase | null => {
    if (!isObject(value)) {
        return null;
    }
    const phaseId = value['phase_id'];
    const sequenceIndex = value['sequence_index'];
    const anchorType = value['anchor_type'];
    const text = value['text'];
    const renderMode = value['render_mode'];
    const prefaceComplete = value['preface_complete'];
    const status = value['status'];
    const collapsed = value['collapsed'];

    if (!isString(phaseId) || !phaseId.trim()) {
        return null;
    }
    if (!isNonNegativeInteger(sequenceIndex)) {
        return null;
    }
    if (expectedSequenceIndex !== null && sequenceIndex !== expectedSequenceIndex) {
        return null;
    }
    if (!isString(anchorType) || !isThinkingTimelineAnchorType(anchorType)) {
        return null;
    }
    if (!isString(text)) {
        return null;
    }
    if (!isString(renderMode) || (renderMode !== 'preface_only' && renderMode !== 'preface_and_thinking' && renderMode !== 'thinking_only')) {
        return null;
    }
    if (!isBoolean(prefaceComplete)) {
        return null;
    }
    if (!isString(status) || (status !== 'running' && status !== 'completed' && status !== 'cancelled' && status !== 'error')) {
        return null;
    }
    if (!isBoolean(collapsed)) {
        return null;
    }

    const mapped: AssistantThinkingPhase = {
        phaseId: phaseId.trim(),
        sequenceIndex: sequenceIndex,
        anchorType: anchorType,
        text: text.trim(),
        renderMode: renderMode,
        prefaceComplete: prefaceComplete,
        status,
        collapsed
    };

    if (anchorType === 'position') {
        const anchorPosition = value['anchor_position'];
        if (!isNonNegativeInteger(anchorPosition)) {
            return null;
        }
        mapped.anchorPosition = anchorPosition;
    } else {
        const anchorCallId = value['anchor_call_id'];
        if (!isString(anchorCallId) || !anchorCallId.trim()) {
            return null;
        }
        mapped.anchorCallId = anchorCallId.trim();
    }

    const prefaceText = value['preface_text'];
    if (renderMode === 'thinking_only') {
        if (prefaceComplete || (prefaceText !== undefined && prefaceText !== null)) {
            return null;
        }
    } else {
        if (!isString(prefaceText) || !prefaceText.trim()) {
            return null;
        }
        if (!prefaceComplete && renderMode !== 'preface_only') {
            return null;
        }
        mapped.prefaceText = prefaceText.trim();
    }

    const durationMs = value['duration_ms'];
    if (durationMs !== undefined) {
        if (!isNonNegativeInteger(durationMs)) {
            return null;
        }
        mapped.durationMs = durationMs;
    }
    const startedAtMs = value['started_at_ms'];
    if (startedAtMs !== undefined) {
        if (!isNonNegativeInteger(startedAtMs)) {
            return null;
        }
        mapped.startedAtMs = startedAtMs;
    }

    return mapped;
};

export { decodeAssistantThinkingPhase };
