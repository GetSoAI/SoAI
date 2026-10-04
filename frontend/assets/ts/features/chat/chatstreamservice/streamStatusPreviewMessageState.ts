/* SoAI - Chat stream status preview message state [frontend/assets/ts/features/chat/chatstreamservice/streamStatusPreviewMessageState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { hasTerminalAssistantState } from '@features/chat/message/assistantTerminalState.ts';

const clearChatStreamStatusPreview = (message: ChatMessage): void => {
    delete message.streamStatusPreviewText;
    delete message.streamStatusPreviewGeneratedAtMs;
    delete message.streamStatusPreviewCooldownMs;
    delete message.streamStatusPreviewTrigger;
};

const applyChatStreamStatusPreview = (message: ChatMessage, inputArguments: { text: string; generatedAtMs: number; cooldownMs: number; trigger: string }): void => {
    message.streamStatusPreviewText = inputArguments.text;
    message.streamStatusPreviewGeneratedAtMs = inputArguments.generatedAtMs;
    message.streamStatusPreviewCooldownMs = inputArguments.cooldownMs;
    message.streamStatusPreviewTrigger = inputArguments.trigger;
};

const STATUS_PREVIEW_CLEARING_EVENT_TYPES: ReadonlySet<string> = new Set(['assistant_text_delta', 'tool_call_created']);

const preserveChatStreamStatusPreview = (source: ChatMessage, target: ChatMessage, sourceRevision: number): void => {
    const { streamStatusPreviewText: text, streamStatusPreviewGeneratedAtMs: generatedAtMs, streamStatusPreviewCooldownMs: cooldownMs, streamStatusPreviewTrigger: trigger } = source;
    if (target.streamStatusPreviewText !== undefined || text === undefined || generatedAtMs === undefined || cooldownMs === undefined || trigger === undefined) return;
    if (hasTerminalAssistantState(target) || (target.assistantEventTimeline ?? []).some((event) => event.assistantRevision > sourceRevision && STATUS_PREVIEW_CLEARING_EVENT_TYPES.has(event.eventType))) return;
    applyChatStreamStatusPreview(target, { text, generatedAtMs, cooldownMs, trigger });
};

export { applyChatStreamStatusPreview, clearChatStreamStatusPreview, preserveChatStreamStatusPreview };
