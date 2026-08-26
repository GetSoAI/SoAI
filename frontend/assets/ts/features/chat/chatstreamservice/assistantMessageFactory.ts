/* SoAI - Chat feature assistant message factory [frontend/assets/ts/features/chat/chatstreamservice/assistantMessageFactory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';

const createInitialAssistantMessage = (inputArguments: { assistantTimestamp: number; assistantTurnTimestamp: number; model: string | null; modelVariantIndex: number; requestId: string }): ChatMessage => ({
    role: 'assistant',
    content: '',
    timestamp: inputArguments.assistantTimestamp,
    assistantTurnAtMs: inputArguments.assistantTurnTimestamp,
    modelVariantIndex: inputArguments.modelVariantIndex,
    requestId: inputArguments.requestId,
    modelId: inputArguments.model,
    assistantEventTimeline: []
});

export { createInitialAssistantMessage };
