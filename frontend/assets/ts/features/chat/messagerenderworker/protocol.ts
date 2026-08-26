/* SoAI - Worker protocol types for chat message rendering [frontend/assets/ts/features/chat/messagerenderworker/protocol.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { LocalizationSnapshot } from '@core/localization/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/message/messageview/activityDurationDisplay.ts';

type IconKey = string;

const buildIconKey = (name: IconName, options?: IconOptions): IconKey => {
    const normalizedOptions = options ? JSON.stringify(options) : '';
    return `${name}::${normalizedOptions}`;
};

type WorkerResources = {
    readonly translationsByKey: Readonly<Record<string, string>>;
    readonly iconsByKey: Readonly<Record<IconKey, string>>;
    readonly localizationSnapshot: LocalizationSnapshot;
};

type RenderContext = {
    readonly epoch: number;
    readonly conversationId: string;
    readonly messageDomId: string;
    readonly messageRevision: number;
    readonly stateSignature: string;
};

type RenderMessageCommonFields = {
    readonly context: RenderContext;
    readonly isRichTextEnabled: boolean;
    readonly codeRecognitionEnabled: boolean;
    readonly isThinkingFeatureEnabled: boolean;
    readonly isShowActivitiesEnabled: boolean;
    readonly activityDurationDisplayMode: ChatActivityDurationDisplayMode;
    readonly isCurrentConversationExecuting: boolean;
    readonly canonicalPlan: AgentCanonicalPlan | null;
    readonly nowMs: number;
    readonly message: ChatMessage;
};

type RenderAssistantBodyFromMessageRequest = RenderMessageCommonFields & {
    readonly type: 'renderAssistantBodyFromMessage';
    readonly requestId: string;
    readonly suppressAssistantActivityWidgets: boolean;
};

type RenderInlineDetailsFromMessageRequest = RenderMessageCommonFields & {
    readonly type: 'renderInlineDetailsFromMessage';
    readonly requestId: string;
    readonly expectedType: 'inline_tool_activity' | 'inline_thinking_activity';
    readonly callId: string;
    readonly timelineSequenceIndex: number | null;
};

type RenderAssistantBodyFromMessageInput = Omit<RenderAssistantBodyFromMessageRequest, 'type' | 'requestId'> & { readonly signal?: AbortSignal | null };
type RenderInlineDetailsFromMessageInput = Omit<RenderInlineDetailsFromMessageRequest, 'type' | 'requestId'> & { readonly signal?: AbortSignal | null };

type InitializeResourcesRequest = {
    readonly type: 'initResources';
    readonly requestId: string;
    readonly resources: WorkerResources;
};

type WorkerRequest = InitializeResourcesRequest | RenderAssistantBodyFromMessageRequest | RenderInlineDetailsFromMessageRequest;

type WorkerOkResponse = { readonly type: 'ok'; readonly requestId: string };
type WorkerRenderResponse = { readonly type: 'rendered'; readonly requestId: string; readonly html: string; readonly context: RenderContext };
type WorkerErrorResponse = { readonly type: 'error'; readonly requestId: string; readonly message: string; readonly details: JsonValue | null };
type WorkerReadyMessage = { readonly type: 'ready' };

type WorkerResponse = WorkerOkResponse | WorkerRenderResponse | WorkerErrorResponse;
type WorkerMessage = WorkerReadyMessage | WorkerResponse;

export { buildIconKey };
export type { IconKey, WorkerResources, RenderContext, RenderMessageCommonFields, WorkerRequest, WorkerMessage, WorkerReadyMessage, WorkerResponse, InitializeResourcesRequest, RenderAssistantBodyFromMessageInput, RenderAssistantBodyFromMessageRequest, RenderInlineDetailsFromMessageInput, RenderInlineDetailsFromMessageRequest };
