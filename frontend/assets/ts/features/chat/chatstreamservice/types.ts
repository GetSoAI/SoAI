/* SoAI - Chat feature stream service public contracts [frontend/assets/ts/features/chat/chatstreamservice/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ChatStreamStatus } from '@core/chat/protocols.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ContentPreviewFeedbackPayload, PreviewContractViolationFeedbackPayload } from '@features/chat/contentPreviewContracts.ts';
import type { AssistantTimelineIndexState } from '@features/chat/assistanteventtimeline/timelineIndexState.ts';
import type { ChatStreamLifecycle } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import type { ChatExecutionModelPlan } from '@features/chat/modelExecutionPreflight.ts';
import type { TokenUsageSnapshot } from '@core/api/contracts/tokenUsageContracts.ts';

type StreamStatus = ChatStreamStatus;
type ChatStreamStartOutcome = StreamStatus | 'detached';

type StreamTransportMode = 'owner' | 'follower';
type HydratedSnapshotApplicationResult = 'active' | 'terminal';
type StreamMutationType = 'replay' | 'initial-timeline' | 'text-delta' | 'timeline-event' | 'image' | 'terminal';
type ChatStreamStartAdmission = 'inactive' | 'busy' | 'unknown';
type ChatTurnAdmissionPhase = 'inactive' | 'starting' | 'streaming' | 'terminalizing' | 'reserved';

interface ChatStreamStopOptions {
    expectedRequestId?: string;
    forcePendingSteers?: boolean;
    reason?: string;
}

type ChatTurnAdmissionStreamIdentity = {
    requestId: string;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
};

interface ChatTurnAdmissionSnapshot {
    conversationId: string;
    phase: ChatTurnAdmissionPhase;
    backendActive: boolean;
    localUiActive: boolean;
    activeStreamIdentity: ChatTurnAdmissionStreamIdentity | null;
    canStop: boolean;
    canSendNow: boolean;
    canQueuePrompt: boolean;
    canSteerPrompt: boolean;
    streamLifecycle: ChatStreamLifecycle;
    startAdmission: ChatStreamStartAdmission;
}

interface ChatStreamSessionMeta {
    conversationId: string;
    conversationTitle: string;
    model: string | null;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
    requestId: string;
}

interface ChatStreamResponseOptions {
    abortSignal?: AbortSignal | null;
    beforeFirstVariantStart?: () => Promise<void>;
    onInitialSyncComplete?: () => void;
    onFirstServerEvent?: () => Promise<void>;
    contentPreviewFeedback?: ContentPreviewFeedbackPayload | null;
    contentPreviewFeedbackSourceMessage?: ChatMessage | null;
    previewContractFeedback?: PreviewContractViolationFeedbackPayload | null;
    executionModelPlan?: ChatExecutionModelPlan | null;
    minimumAssistantTurnAtMs?: number | null;
    reportRequestFailure?: boolean;
    skipInitialMessageSync?: boolean;
}

interface ChatStreamStartOptions {
    conversationId: string;
    conversationTitle: string;
    model: string | null;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
    requestBody: JsonObject;
    requestId: string;
    abortSignal?: AbortSignal | null;
    onFirstServerEvent?: (() => Promise<void>) | null;
    contentPreviewFeedback?: ContentPreviewFeedbackPayload | null;
    previewContractFeedback?: PreviewContractViolationFeedbackPayload | null;
}

interface ChatStreamSession extends ChatStreamSessionMeta {
    transportMode: StreamTransportMode;
    status: StreamStatus;
    abortController: AbortController;
    countsAsStreaming: boolean;
    assistantMessage: ChatMessage;
    assistantRevision: number;
    assistantTimelineIndexState: AssistantTimelineIndexState;
    usagePreview: TokenUsageSnapshot | null;
    pendingCancellation: { reason: string; forcePendingSteers?: boolean } | null;
    ownerReleaseRequested: boolean;
    ownerReleaseListener: (() => void) | null;
    onFirstServerEvent?: (() => Promise<void>) | null;
    firstServerEventHandled: boolean;
    active: boolean;
    lastError: JsonValue | null;
    promise: Promise<void>;
}

interface StreamUpdate {
    conversationId: string;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    status: StreamStatus;
    countsAsStreaming: boolean;
    message: ChatMessage;
    assistantRevision: number;
    modelVariantIndex: number;
    requestId: string;
    usagePreview: TokenUsageSnapshot | null;
    mutation: {
        type: StreamMutationType;
        textDelta: string | null;
    };
}

interface InterruptedStreamSnapshot {
    conversationId: string;
    requestId: string;
    assistantMessage: ChatMessage;
    assistantTimestamp: number;
    assistantTurnTimestamp: number;
    modelVariantIndex: number;
}

type StreamListener = (update: StreamUpdate) => Promise<void> | void;

type ChatNotifyPrefs = {
    notifyOnCompletion: boolean;
    notifyOnError: boolean;
};

export { type ChatNotifyPrefs, type ChatStreamLifecycle, type ChatStreamResponseOptions, type ChatStreamSession, type ChatStreamSessionMeta, type ChatStreamStartAdmission, type ChatStreamStartOptions, type ChatStreamStartOutcome, type ChatStreamStopOptions, type ChatTurnAdmissionPhase, type ChatTurnAdmissionSnapshot, type ChatTurnAdmissionStreamIdentity, type HydratedSnapshotApplicationResult, type InterruptedStreamSnapshot, type StreamListener, type StreamMutationType, type StreamTransportMode, type StreamUpdate };
