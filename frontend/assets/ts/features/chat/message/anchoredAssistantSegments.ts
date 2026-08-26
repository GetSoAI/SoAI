/* SoAI - Chat feature anchored assistant segments [frontend/assets/ts/features/chat/message/anchoredAssistantSegments.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { compareAssistantChronologyRenderEntry, type AssistantChronologyRenderEntry } from '@features/chat/assistanteventtimeline/timelineChronology.ts';
import type { MessageSegment, TextSegment } from '@features/chat/message/messageSegments.ts';

type AnchoredAssistantActivity = AssistantChronologyRenderEntry;

interface AnchoredAssistantTextState {
    signatureSequence: number | null;
    text: string;
    active: boolean;
    terminal: boolean;
}

const sliceTextCodePoints = (codePoints: string[], start: number, end: number): string => {
    if (end <= start) {
        return '';
    }
    return codePoints.slice(start, end).join('');
};

const buildTextSegment = (text: string, signatureSequence: number | null, active: boolean): TextSegment => {
    const segment: TextSegment = {
        type: 'text',
        text,
        value: text
    };
    if (signatureSequence !== null) {
        segment.signatureSequence = signatureSequence;
    }
    if (active) {
        segment.isStreamingActive = true;
    }
    return segment;
};

const resolveActivityDiagnosticId = (activity: AnchoredAssistantActivity): string => {
    const segment = activity.segment;
    if (segment.type === 'inline_tool_activity' || segment.type === 'inline_thinking_activity' || segment.type === 'inline_action_update') {
        return segment.callId;
    }
    return 'none';
};

const appendVisibleTextRange = (segments: MessageSegment[], codePoints: string[], start: number, end: number, signatureSequence: number | null, active: boolean): void => {
    const text = sliceTextCodePoints(codePoints, start, end);
    if (!text) {
        return;
    }
    segments.push(buildTextSegment(text, signatureSequence, active));
};

const validateResolvedActivityAnchors = (textState: AnchoredAssistantTextState, activities: AnchoredAssistantActivity[]): AnchoredAssistantActivity[] => {
    const textLength = Array.from(textState.text).length;
    const resolved: AnchoredAssistantActivity[] = [];
    for (const activity of activities) {
        if (activity.contentIndexBefore > textLength) {
            if (textState.terminal) {
                throw new Error(`Assistant event timeline activity anchor exceeds final assistant visible text length. sequence=${String(activity.eventSequence)} call_id=${resolveActivityDiagnosticId(activity)} anchor=${String(activity.contentIndexBefore)} final_length=${String(textLength)}`);
            }
            continue;
        }
        resolved.push(activity);
    }
    return resolved;
};

const resolveAnchoredAssistantSegments = (textState: AnchoredAssistantTextState, activities: AnchoredAssistantActivity[], trailingSegments: MessageSegment[]): MessageSegment[] => {
    const codePoints = Array.from(textState.text);
    const textLength = codePoints.length;
    const orderedActivities = validateResolvedActivityAnchors(textState, activities).sort(compareAssistantChronologyRenderEntry);
    const segments: MessageSegment[] = [];
    let cursor = 0;
    let activityIndex = 0;

    while (activityIndex < orderedActivities.length) {
        const activity = orderedActivities[activityIndex];
        if (!activity) {
            break;
        }
        appendVisibleTextRange(segments, codePoints, cursor, activity.contentIndexBefore, textState.signatureSequence, false);
        cursor = activity.contentIndexBefore;
        while (activityIndex < orderedActivities.length) {
            const nextActivity = orderedActivities[activityIndex];
            if (!nextActivity) {
                break;
            }
            if (nextActivity.contentIndexBefore !== activity.contentIndexBefore) {
                break;
            }
            segments.push(nextActivity.segment);
            activityIndex += 1;
        }
    }

    appendVisibleTextRange(segments, codePoints, cursor, textLength, textState.signatureSequence, textState.active);
    segments.push(...trailingSegments);
    return segments;
};

export { resolveAnchoredAssistantSegments };
export type { AnchoredAssistantActivity, AnchoredAssistantTextState };
