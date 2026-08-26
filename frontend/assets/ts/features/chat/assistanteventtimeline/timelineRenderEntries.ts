/* SoAI - Assistant event timeline render entry resolution [frontend/assets/ts/features/chat/assistanteventtimeline/timelineRenderEntries.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isNumber, isString } from '@core/typeGuards.ts';
import { resolveThinkingDisplayContract } from '@features/chat/assistanteventtimeline/thinkingDisplayContract.ts';
import type { AssistantChronologyRenderEntry } from '@features/chat/assistanteventtimeline/timelineChronology.ts';
import { resolveAssistantTimelineActivitySegments, resolveAssistantTimelineOverlays, resolveCollapsedOverrideMap } from '@features/chat/assistanteventtimeline/timelineIndexResolution.ts';
import type { AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { ChatMessage, ThinkingTimelineItem, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import { CONTEXT_COMPACTION_TOOL_LEAF, isRemovedContextCompactionResult } from '@features/chat/message/contextcompaction/detection.ts';
import { applySubagentChildToolCollapsedOverrides } from '@features/chat/message/messageview/subagentToolCallSegments.ts';
import type { InlineActionUpdateSegment, InlineThinkingActivitySegment, InlineToolActivitySegment } from '@features/chat/message/messageSegments.ts';
import { requireAssistantVariantIdentity } from '@core/chat/assistantIdentity.ts';
import { normalizeToolLeafName } from '@features/chat/toolactivity/toolLeafName.ts';

const THINKING_PREFACE_ORDER = 0;
const THINKING_ACTIVITY_ORDER = 1;

const requireTimelineSequence = (map: Map<string, number>, callId: string, context: string): number => {
    const sequence = map.get(callId);
    if (sequence === undefined) {
        throw new Error(`Assistant event timeline ordering is missing sequence metadata for ${context} "${callId}".`);
    }
    return sequence;
};

const resolveRevisionSequence = (signatureSequence: number | undefined, eventSequence: number): number => {
    if (typeof signatureSequence === 'number' && Number.isFinite(signatureSequence) && signatureSequence >= 0) {
        return Math.floor(signatureSequence);
    }
    return eventSequence;
};

const buildInlineToolSegmentFromItem = (item: ToolActivityItem, nestedCollapsedOverrides: Map<string, boolean>, identity: { assistantTurnTimestamp: number; modelVariantIndex: number }): InlineToolActivitySegment => {
    const segment: InlineToolActivitySegment = {
        type: 'inline_tool_activity',
        callId: item.callId,
        toolName: item.toolName,
        status: item.status,
        contentIndexBefore: item.contentIndexBefore,
        assistantTurnAtMs: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex,
        collapsed: item.collapsed !== false
    };
    const signatureSequence = resolveRevisionSequence(item.signatureSequence, item.sequenceIndex);
    segment.signatureSequence = signatureSequence;
    if (item.inputArguments !== undefined) {
        segment.inputArguments = item.inputArguments;
    }
    if (isArray(item.codeDiffs) && item.codeDiffs.length > 0) {
        segment.codeDiffs = item.codeDiffs;
    }
    if (item.result !== undefined) {
        segment.result = normalizeToolLeafName(item.toolName) === 'subagent_spawn' ? applySubagentChildToolCollapsedOverrides(item.result, item.callId, nestedCollapsedOverrides) : item.result;
    }
    if (item.error !== undefined) {
        segment.error = item.error;
    }
    if (item.durationMs !== undefined) {
        segment.durationMs = item.durationMs;
    }
    if (item.startedAtMs !== undefined) {
        segment.startedAtMs = item.startedAtMs;
    }
    return segment;
};

const isRemovedContextCompactionToolActivity = (item: ToolActivityItem): boolean => {
    return normalizeToolLeafName(item.toolName) === CONTEXT_COMPACTION_TOOL_LEAF && isRemovedContextCompactionResult(item.result);
};

const resolveThinkingAnchor = (phase: ThinkingTimelineItem, timelineIndexState: AssistantTimelineIndexState): number | null => {
    const renderAnchor = timelineIndexState.thinkingRenderAnchorByPhaseId.get(phase.phaseId);
    if (renderAnchor !== undefined) {
        return renderAnchor;
    }
    if (phase.anchorType === 'position') {
        const anchorPosition = phase.anchorPosition;
        if (!isNumber(anchorPosition) || !Number.isFinite(anchorPosition) || !Number.isInteger(anchorPosition) || anchorPosition < 0) {
            throw new Error(`Thinking timeline phase ${phase.phaseId} has invalid anchor_position`);
        }
        return anchorPosition;
    }
    const anchorCallId = phase.anchorCallId;
    if (!isString(anchorCallId) || !anchorCallId.trim()) {
        throw new Error(`Thinking timeline phase ${phase.phaseId} is missing anchor_call_id`);
    }
    const anchor = timelineIndexState.toolRenderAnchorByCallId.get(anchorCallId.trim());
    if (anchor === undefined) {
        if (timelineIndexState.hasTerminalEvent) {
            throw new Error(`Thinking timeline phase ${phase.phaseId} references unknown anchor_call_id "${anchorCallId.trim()}".`);
        }
        return null;
    }
    return anchor;
};

const buildThinkingRenderEntries = (timeline: ThinkingTimelineItem[], timelineIndexState: AssistantTimelineIndexState): AssistantChronologyRenderEntry[] => {
    const entries: AssistantChronologyRenderEntry[] = [];
    for (const phase of timeline) {
        const contentIndexBefore = resolveThinkingAnchor(phase, timelineIndexState);
        if (contentIndexBefore === null) {
            continue;
        }
        const eventSequence = requireTimelineSequence(timelineIndexState.thinkingSequenceByCallId, phase.phaseId, 'thinking phase');
        const revisionSequence = resolveRevisionSequence(phase.signatureSequence, eventSequence);
        const display = resolveThinkingDisplayContract(phase);
        if (display.prefaceText !== null) {
            const prefaceSegment: InlineActionUpdateSegment = {
                type: 'inline_action_update',
                callId: phase.phaseId,
                timelineSequenceIndex: phase.sequenceIndex,
                contentIndexBefore: contentIndexBefore,
                text: display.prefaceText,
                signatureSequence: revisionSequence
            };
            entries.push({ contentIndexBefore, eventSequence, revisionSequence, sameAnchorOrder: THINKING_PREFACE_ORDER, segment: prefaceSegment });
        }
        if (!display.renderThinkingActivity) {
            continue;
        }
        const thinkingSegment: InlineThinkingActivitySegment = {
            type: 'inline_thinking_activity',
            callId: phase.phaseId,
            timelineSequenceIndex: phase.sequenceIndex,
            contentIndexBefore: contentIndexBefore,
            status: phase.status,
            text: display.thinkingText,
            signatureSequence: revisionSequence,
            collapsed: phase.collapsed !== false
        };
        if (phase.durationMs !== undefined) {
            if (!isNumber(phase.durationMs) || !Number.isFinite(phase.durationMs) || phase.durationMs < 0) {
                throw new Error(`Thinking timeline phase ${phase.phaseId} duration_ms must be a non-negative integer when provided`);
            }
            thinkingSegment.durationMs = Math.floor(phase.durationMs);
        }
        if (phase.startedAtMs !== undefined) {
            if (!isNumber(phase.startedAtMs) || !Number.isFinite(phase.startedAtMs) || phase.startedAtMs < 0) {
                throw new Error(`Thinking timeline phase ${phase.phaseId} started_at_ms must be a non-negative integer when provided`);
            }
            thinkingSegment.startedAtMs = Math.floor(phase.startedAtMs);
        }
        entries.push({ contentIndexBefore, eventSequence, revisionSequence, sameAnchorOrder: THINKING_ACTIVITY_ORDER, segment: thinkingSegment });
    }
    return entries;
};

const resolveAssistantTimelineRenderEntries = (message: ChatMessage, timelineIndexState: AssistantTimelineIndexState): AssistantChronologyRenderEntry[] => {
    const overlays = resolveAssistantTimelineOverlays(message, timelineIndexState);
    const nestedCollapsedOverrides = resolveCollapsedOverrideMap(message.inlineToolCollapsedByCallId);
    const identity = requireAssistantVariantIdentity({
        assistantTurnTimestamp: message.assistantTurnAtMs,
        modelVariantIndex: message.modelVariantIndex,
        context: 'Assistant tool segments'
    });
    const entries: AssistantChronologyRenderEntry[] = [...resolveAssistantTimelineActivitySegments(timelineIndexState)];
    for (const item of overlays.toolActivity) {
        if (isRemovedContextCompactionToolActivity(item)) {
            continue;
        }
        const eventSequence = requireTimelineSequence(timelineIndexState.toolRenderSequenceByCallId, item.callId, 'tool activity');
        entries.push({
            contentIndexBefore: item.contentIndexBefore,
            eventSequence,
            revisionSequence: resolveRevisionSequence(item.signatureSequence, eventSequence),
            segment: buildInlineToolSegmentFromItem(item, nestedCollapsedOverrides, identity)
        });
    }
    entries.push(...buildThinkingRenderEntries(overlays.thinkingTimeline, timelineIndexState));
    return entries;
};

export { resolveAssistantTimelineRenderEntries };
