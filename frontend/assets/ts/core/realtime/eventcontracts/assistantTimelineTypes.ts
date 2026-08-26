/* SoAI - Frontend assistant timeline domain contracts [frontend/assets/ts/core/realtime/eventcontracts/assistantTimelineTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ToolActivityCodeDiff } from '@core/chat/codeDiffParsing.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';

type AssistantActivityStatus = 'running' | 'completed' | 'cancelled' | 'error';

interface AssistantActivityState {
    status: AssistantActivityStatus;
    startedAtMs: number;
    durationMs: number;
    reason?: string;
    errorType?: string;
}

interface AssistantTimelineTool {
    callId: string;
    toolName: string;
    status: 'pending' | AssistantActivityStatus;
    sequenceIndex: number;
    messageIndex: number;
    contentIndexBefore: number;
    thinkingIndexBefore: number;
    collapsed: boolean;
    inputArguments?: JsonValue;
    result?: JsonValue;
    error?: string;
    durationMs?: number;
    startedAtMs?: number;
    completedAtMs?: number;
    liveRevision?: number;
    lastLiveSequence?: number;
    lastLiveEventAtMs?: number;
    syncStatus?: 'in_sync' | 'out_of_sync';
    thinkingDurationBeforeMs?: number;
    assistantTurnAtMs?: number;
    modelVariantIndex?: number;
    turnId?: string;
    iterationIndex?: number;
    codeDiffs?: ToolActivityCodeDiff[];
}

type ThinkingTimelineAnchorType = 'before_call' | 'after_call' | 'position';

interface AssistantThinkingPhase {
    phaseId: string;
    sequenceIndex: number;
    anchorType: ThinkingTimelineAnchorType;
    anchorCallId?: string;
    anchorPosition?: number;
    text: string;
    renderMode: 'preface_only' | 'preface_and_thinking' | 'thinking_only';
    prefaceText?: string;
    prefaceComplete: boolean;
    status: AssistantActivityStatus;
    collapsed: boolean;
    durationMs?: number;
    startedAtMs?: number;
}

interface AssistantTimelineImage {
    url: string;
}

interface AssistantCompletedUsage {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    usageSource: string;
}

interface AssistantTimelinePayload {
    assistantAtMs?: number;
    assistantTurnAtMs?: number;
    assistantRevision?: number;
    modelVariantIndex?: number;
    delta?: string;
    image?: AssistantTimelineImage;
    tool?: AssistantTimelineTool;
    thinkingPhase?: AssistantThinkingPhase;
    loadingActivity?: AssistantActivityState;
    processingActivity?: AssistantActivityState;
    waitForUserActivity?: AssistantActivityState;
    usagePreview?: TokenUsageSnapshot;
    usage?: AssistantCompletedUsage | null;
    finishReason?: string | null;
    previewContract?: JsonValue;
    reason?: string | null;
    code?: string | null;
    message?: string | null;
    referenceId?: string | null;
}

interface AssistantEventTimelineItem {
    sourceSequenceStart?: number;
    sequence: number;
    assistantRevision: number;
    eventType: string;
    payload: AssistantTimelinePayload;
}

type AssistantTimelineType = 'canonical' | 'projection';

export type { AssistantActivityState, AssistantActivityStatus, AssistantCompletedUsage, AssistantEventTimelineItem, AssistantThinkingPhase, AssistantTimelineImage, AssistantTimelinePayload, AssistantTimelineTool, AssistantTimelineType, ThinkingTimelineAnchorType };
