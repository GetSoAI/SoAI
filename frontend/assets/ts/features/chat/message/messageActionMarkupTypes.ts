/* SoAI - Chat message action markup contracts [frontend/assets/ts/features/chat/message/messageActionMarkupTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AssistantResponseDurationState } from '@features/chat/message/assistantResponseDuration.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { MessageActionButtonRenderContext } from '@features/chat/message/messageActionButtons.ts';
import type { ConversationRunningActivitySnapshot } from '@features/chat/storage/storageModels.ts';
import type { RunningActivitySummary } from '@features/chat/toolactivity/runningActivitySummary.ts';

interface MessageActionMarkupContext extends MessageActionButtonRenderContext {
    escapeHtml(value: string): string;
    isConversationExecuting(conversationId: string): boolean;
    getCurrentConversationId(): string | null;
    getCurrentRunningActivitySnapshot(): ConversationRunningActivitySnapshot | null;
    resolveAssistantResponseDuration(message: ChatMessage, nowMs: number): AssistantResponseDurationState;
    resolveRunningActivitySummaryForMarkup(message: ChatMessage, nowMs: number): RunningActivitySummary;
}

export type { MessageActionMarkupContext };
