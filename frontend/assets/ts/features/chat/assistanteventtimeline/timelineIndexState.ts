/* SoAI - Chat feature timeline index state [frontend/assets/ts/features/chat/assistanteventtimeline/timelineIndexState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantEventTimelineItem, ThinkingTimelineItem, ToolActivityItem } from '@features/chat/ChatTypes.ts';
import type { AssistantChronologyRenderEntry } from '@features/chat/assistanteventtimeline/timelineChronology.ts';

type ActivitySegmentEntry = AssistantChronologyRenderEntry;
type ToolActivitySource = 'lifecycle' | 'projection';

export interface AssistantTimelineOverlays {
    toolActivity: ToolActivityItem[];
    thinkingTimeline: ThinkingTimelineItem[];
}

interface ActivityLifecycleEntry {
    contentIndexBefore: number;
    eventSequence: number;
    revisionSequence: number;
    segment: AssistantChronologyRenderEntry['segment'];
}

export interface AssistantTimelineIndexState {
    timelineReference: AssistantEventTimelineItem[] | null;
    timelineProjectionHash: string;
    timelineLatestAssistantRevision: number;
    processedLength: number;
    processedEventSignatures: string[];
    toolRenderSequenceByCallId: Map<string, number>;
    toolLifecycleStatusRankByCallId: Map<string, number>;
    thinkingSequenceByCallId: Map<string, number>;
    thinkingRenderAnchorByPhaseId: Map<string, number>;
    toolRenderAnchorByCallId: Map<string, number>;
    toolSourceByCallId: Map<string, ToolActivitySource>;
    hasAssistantTextDeltas: boolean;
    assistantVisibleText: string;
    assistantVisibleTextCodePointLength: number;
    assistantTextIsStreamingActive: boolean;
    hasTerminalEvent: boolean;
    hasAssistantImages: boolean;
    toolActivityByCallId: Map<string, ToolActivityItem>;
    toolCallIdBySequenceIndex: Map<number, string>;
    thinkingBySequenceIndex: Map<number, ThinkingTimelineItem>;
    thinkingPhaseIdBySequenceIndex: Map<number, string>;
    thinkingPhaseSequenceIndexByPhaseId: Map<string, number>;
    timelineSegmentByLifecycleKey: Map<string, ActivityLifecycleEntry>;
    openStatusActivityLifecycleKeyByType: Map<string, string>;
    statusActivityLifecycleKeyByTypeAndStartedAt: Map<string, string>;
    cachedToolActivity: ToolActivityItem[] | null;
    cachedThinkingTimeline: ThinkingTimelineItem[] | null;
    cachedTimelineSegments: ActivitySegmentEntry[] | null;
}

const createAssistantTimelineIndexState = (): AssistantTimelineIndexState => {
    return {
        timelineReference: null,
        timelineProjectionHash: '',
        timelineLatestAssistantRevision: 0,
        processedLength: 0,
        processedEventSignatures: [],
        toolRenderSequenceByCallId: new Map(),
        toolLifecycleStatusRankByCallId: new Map(),
        thinkingSequenceByCallId: new Map(),
        thinkingRenderAnchorByPhaseId: new Map(),
        toolRenderAnchorByCallId: new Map(),
        toolSourceByCallId: new Map(),
        hasAssistantTextDeltas: false,
        assistantVisibleText: '',
        assistantVisibleTextCodePointLength: 0,
        assistantTextIsStreamingActive: false,
        hasTerminalEvent: false,
        hasAssistantImages: false,
        toolActivityByCallId: new Map(),
        toolCallIdBySequenceIndex: new Map(),
        thinkingBySequenceIndex: new Map(),
        thinkingPhaseIdBySequenceIndex: new Map(),
        thinkingPhaseSequenceIndexByPhaseId: new Map(),
        timelineSegmentByLifecycleKey: new Map(),
        openStatusActivityLifecycleKeyByType: new Map(),
        statusActivityLifecycleKeyByTypeAndStartedAt: new Map(),
        cachedToolActivity: null,
        cachedThinkingTimeline: null,
        cachedTimelineSegments: null
    };
};

const resetAssistantTimelineIndexState = (state: AssistantTimelineIndexState): void => {
    state.processedLength = 0;
    state.timelineReference = null;
    state.timelineProjectionHash = '';
    state.timelineLatestAssistantRevision = 0;
    state.processedEventSignatures = [];
    state.toolRenderSequenceByCallId.clear();
    state.toolLifecycleStatusRankByCallId.clear();
    state.thinkingSequenceByCallId.clear();
    state.thinkingRenderAnchorByPhaseId.clear();
    state.toolRenderAnchorByCallId.clear();
    state.toolSourceByCallId.clear();
    state.hasAssistantTextDeltas = false;
    state.assistantVisibleText = '';
    state.assistantVisibleTextCodePointLength = 0;
    state.assistantTextIsStreamingActive = false;
    state.hasTerminalEvent = false;
    state.hasAssistantImages = false;
    state.toolActivityByCallId.clear();
    state.toolCallIdBySequenceIndex.clear();
    state.thinkingBySequenceIndex.clear();
    state.thinkingPhaseIdBySequenceIndex.clear();
    state.thinkingPhaseSequenceIndexByPhaseId.clear();
    state.timelineSegmentByLifecycleKey.clear();
    state.openStatusActivityLifecycleKeyByType.clear();
    state.statusActivityLifecycleKeyByTypeAndStartedAt.clear();
    state.cachedToolActivity = null;
    state.cachedThinkingTimeline = null;
    state.cachedTimelineSegments = null;
};

export { createAssistantTimelineIndexState, resetAssistantTimelineIndexState };
export type { ActivitySegmentEntry, ToolActivitySource };
