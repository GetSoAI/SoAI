/* SoAI - Chat feature API message mapping contracts [frontend/assets/ts/features/chat/apimessagemapping/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessageRole } from '@core/chat/messageRoles.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ToolCall } from '@features/chat/ChatTypes.ts';
import type { AssistantEventTimelineItem } from '@core/realtime/eventcontracts/assistantTimelineTypes.ts';

type ApiChatMessage = {
    role: MessageRole;
    content: string | JsonValue[];
    timestamp: number;
    assistantTurnAtMs?: number;
    modelVariantIndex?: number;
    name?: string;
    toolCalls?: ToolCall[];
    assistantEventTimeline?: AssistantEventTimelineItem[];
    toolCallId?: string;
    requestId?: string;
    modelId?: string;
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
    usageSource?: string;
    generationLatencyMs?: number;
    generationSpeedTokensPerSec?: number;
    finishReason?: string;
    thinkingTailDurationMs?: number;
};

interface ConversationContract {
    messages?: JsonValue[];
    title?: string;
    isFavorite?: boolean;
    color?: string | null | undefined;
    isAutomation?: boolean;
}

export type { ApiChatMessage, ConversationContract };
