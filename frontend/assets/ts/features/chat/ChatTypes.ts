/* SoAI - Shared chat feature data contracts [frontend/assets/ts/features/chat/ChatTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessageRole } from '@core/chat/messageRoles.ts';
import type { ConversationMessageType } from '@core/chat/conversationMessageType.ts';
import type { ConversationSettingsAuthority } from '@core/chat/conversationSettingsAuthority.ts';
import type { MessagingPlatform } from '@core/chat/conversationSource.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ToolActivityCodeDiff } from '@core/chat/codeDiffParsing.ts';
import type { AssistantCompletedUsage, AssistantEventTimelineItem, AssistantTimelineType } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import type { WebuiMessageContentPart } from '@core/api/contracts/webuiMessageContentPartContract.ts';
import type { ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';
import type { SoaiPathDraftRecord } from '@features/chat/attachments/soaiPathDraftRecords.ts';
import type { ContentPreviewFeedbackState } from '@features/chat/contentPreviewContracts.ts';

interface ImageReference {
    url?: string;
    detail?: string;
    previewUrl?: string;
}

interface BaseSegment {
    type?: string;
}

interface TextSegment extends BaseSegment {
    type: 'text';
    text?: string;
    value?: string;
}

interface ThinkingSegment extends BaseSegment {
    type: 'thinking';
    text?: string;
    value?: string;
}

interface ImageSegment extends BaseSegment {
    type: 'image' | 'image_url';
    imageUrl?: string | ImageReference;
    image?: string | ImageReference;
    url?: string;
    src?: string;
    title?: string;
    alt?: string;
}

interface ToolFunctionCall {
    name?: string;
    serializedArguments?: string;
}

interface ToolCallSegment extends BaseSegment {
    type: 'tool_call';
    id?: string;
    name?: string;
    function?: ToolFunctionCall;
    metadata?: JsonObject;
    toolArguments?: JsonValue;
    functionArguments?: JsonValue;
    input?: JsonValue;
    parameters?: JsonValue;
}

interface ToolCall extends BaseSegment {
    id?: string | null;
    index?: number;
    type?: string;
    function?: ToolFunctionCall | null;
    output?: string;
    toolArguments?: JsonValue;
    functionArguments?: JsonValue;
    input?: JsonValue;
    parameters?: JsonValue;
}

type StructuredContentSegment = TextSegment | ThinkingSegment | ImageSegment | ToolCallSegment;

type ChatContentSegment = StructuredContentSegment | WebuiMessageContentPart | string;

type ChatContent = string | ChatContentSegment | Array<ChatContentSegment> | null;

interface SoaiCompactionPromptMessage {
    role: string;
    content: string;
    name?: string;
}

interface SoaiCompactionMarker {
    toolCallId?: string | null;
    status?: string;
    output?: string | null;
    trigger?: string | null;
    model?: string | null;
    details?: JsonObject;
    promptMessage?: SoaiCompactionPromptMessage;
    boundaryRemovedAtMs?: number;
    boundaryRemovedReason?: string;
    sequenceIndex?: number;
    isActiveBoundary?: boolean;
}

interface ChatMessageFields {
    id?: string | number;
    content?: ChatContent;
    timestamp?: number;
    assistantTurnAtMs?: number | null;
    modelVariantIndex?: number | null;
    requestId?: string | null;
    modelId?: string | null;
    name?: string;
    toolCallId?: string;
    soaiConversationInputId?: string;
    messagingSenderDisplayName?: string;
    messagingSenderId?: string;
    messageType?: ConversationMessageType;
    toolCalls?: ToolCall[];
    finishReason?: string | null;
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
    usageSource?: string;
    generationLatencyMs?: number;
    generationSpeedTokensPerSec?: number;
    thinkingTailDurationMs?: number;
    assistantEventTimeline?: AssistantEventTimelineItem[];
    assistantTimelineType?: AssistantTimelineType;
    toolCallProjections?: ToolActivityItem[];
    contentPreviewFeedbackState?: ContentPreviewFeedbackState;
    soaiMessageType?: string;
    soaiCompaction?: SoaiCompactionMarker;
    soaiCompactionStats?: { count: number; tokensSaved: number };
    streamStatusPreviewText?: string;
    streamStatusPreviewGeneratedAtMs?: number;
    streamStatusPreviewCooldownMs?: number;
    streamStatusPreviewTrigger?: string;
    inlineThinkingCollapsedByCallId?: Record<string, boolean>;
    inlineToolCollapsedByCallId?: Record<string, boolean>;
    errorCode?: string;
    usage?: AssistantCompletedUsage;
    attachments?: JsonValue;
    images?: JsonValue;
    documents?: JsonValue;
    message?: JsonObject;
}

type ChatMessage = ChatMessageFields & ({ role: 'system' } | { role: 'developer' } | { role: 'user' } | { role: 'assistant' } | { role: 'tool' });

type ConversationMessage = ChatMessage;

interface ConversationContract {
    id?: string;
    title?: string;
    messages: ConversationMessage[];
    modelSettings?: ConversationModelSettings;
    createdAt?: number;
    updatedAt?: number;
    isAutomation?: boolean;
    isMessaging?: boolean;
    messagingPlatform?: MessagingPlatform | null;
    messagingAccountLabel?: string | null;
    messagingAccountSnapshotId?: string | null;
    isFavorite?: boolean;
    color?: string | null;
    isArchived?: boolean;
    compactionCount?: number;
    compactionTokensSaved?: number;
    messageCount?: number;
    history?: {
        totalCount: number;
        hasNewer: boolean;
    };
    effectiveWorkspacePath?: string;
    effectiveWorkspaceRootFingerprint?: string;
    settingsAuthority?: ConversationSettingsAuthority;
}

type ToolActivityStatus = 'pending' | 'running' | 'completed' | 'cancelled' | 'error';

interface ToolActivityItem {
    callId: string;
    toolName: string;
    status: ToolActivityStatus;
    signatureSequence?: number;
    inputArguments?: JsonValue;
    codeDiffs?: ToolActivityCodeDiff[];
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
    sequenceIndex: number;
    contentIndexBefore: number;
    thinkingIndexBefore: number;
    collapsed: boolean;
}

type ThinkingTimelineAnchorType = 'before_call' | 'after_call' | 'position';

interface ThinkingTimelineItem {
    phaseId: string;
    sequenceIndex: number;
    anchorType: ThinkingTimelineAnchorType;
    anchorCallId?: string;
    anchorPosition?: number;
    text: string;
    renderMode: 'preface_only' | 'preface_and_thinking' | 'thinking_only';
    prefaceText?: string;
    prefaceComplete: boolean;
    status: 'running' | 'completed' | 'cancelled' | 'error';
    collapsed: boolean;
    signatureSequence?: number;
    durationMs?: number;
    startedAtMs?: number;
}

interface ChatErrorHandler {
    debug?: (scope: string, message: string, error?: TelemetryValue) => void;
    info?: (scope: string, message: string, error?: TelemetryValue) => void;
    warn?: (scope: string, message: string, error?: TelemetryValue) => void;
    error?: (scope: string, message: string, error?: TelemetryValue) => void;
}

interface ChatAttachmentErrorHandler {
    (error: Error, title: string, options?: { notify?: boolean }): void;
}

interface ChatAttachment {
    id: string;
    file: File | null;
    name: string;
    size: number;
    type: string;
    isImage: boolean;
    parseStatus: 'ready' | 'processing' | 'error';
    conversationId?: string;
    clientAttachmentId?: string;
    clientRequestId?: string;
    attachmentId?: string;
    fileId?: string;
    mimeType?: string;
    sizeBytes?: number;
    previewType?: string;
    providerMode?: string | null;
    providerTextTruncated?: boolean;
    parseState?: 'pending' | 'ready' | 'failed';
    state?: string;
    attachmentRevision?: number;
    createdAtMs?: number;
    updatedAtMs?: number;
    downloadUrl?: string;
    ragConversationId?: string;
    ragDocumentId?: string;
    ragTaskId?: string;
    previewUrl?: string;
    previewText?: string;
    parseError?: string;
    extractedText?: string;
    extractionNote?: string;
    extractionTruncated?: boolean;
    soaiPathRecord?: SoaiPathDraftRecord;
}

interface ChatAttachmentUIManager {
    clearAttachedFiles(): void;
    updateInputState(): void;
    updateAttachmentsPreview(): void;
}

interface ChatConversationUIManager {
    applyExecutionControls(): void;
    setAutoScrollEnabled(enabled: boolean): void;
}

export type { MessageRole, ImageReference, BaseSegment, TextSegment, ThinkingSegment, ImageSegment, ToolFunctionCall, ToolCallSegment, ToolCall, StructuredContentSegment, ChatContentSegment, ChatContent, SoaiCompactionPromptMessage, SoaiCompactionMarker, ChatMessage, ConversationMessage, ConversationContract, ToolActivityStatus, ToolActivityCodeDiff, ToolActivityItem, ThinkingTimelineAnchorType, ThinkingTimelineItem, AssistantEventTimelineItem, ChatErrorHandler, ChatAttachmentErrorHandler, ChatAttachment, ChatAttachmentUIManager, ChatConversationUIManager };
