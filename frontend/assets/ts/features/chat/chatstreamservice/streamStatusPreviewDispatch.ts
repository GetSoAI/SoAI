/* SoAI - Chat stream status preview dispatch [frontend/assets/ts/features/chat/chatstreamservice/streamStatusPreviewDispatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatStreamSession } from '@features/chat/chatstreamservice/types.ts';
import type { StreamRuntime } from '@features/chat/chatstreamservice/contracts.ts';
import type { ChatStreamStatusPreviewEventEnvelope } from '@core/realtime/eventcontracts/chatStreamStatusPreview.ts';
import type { StreamRequestDispositionRegistry } from '@features/chat/chatstreamservice/streamRequestDispositionRegistry.ts';
import { translateChatStreamPreviewKey } from '@features/chat/chatstreamservice/streamPreviewTranslation.ts';
import { applyChatStreamStatusPreview } from '@features/chat/chatstreamservice/streamStatusPreviewMessageState.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

type DispatchChatStreamStatusPreviewArguments = {
    envelope: ChatStreamStatusPreviewEventEnvelope;
    sessions: Map<string, ChatStreamSession>;
    runtime: StreamRuntime;
    requestDispositions: StreamRequestDispositionRegistry;
};

const dispatchChatStreamStatusPreview = (inputArguments: DispatchChatStreamStatusPreviewArguments): void => {
    const envelope = inputArguments.envelope;
    const conversationId = normalizeConversationId(envelope.convId);
    if (!conversationId) {
        throw new Error('Chat stream status preview event requires a valid conversation id.');
    }
    const session = inputArguments.sessions.get(conversationId);
    if (!session || !session.active || session.status !== 'streaming') {
        return;
    }
    if (session.requestId !== envelope.requestId.trim()) {
        return;
    }
    const suppressed = session.transportMode === 'follower' ? inputArguments.requestDispositions.shouldIgnorePassiveStreamEvent(conversationId, session.requestId) : inputArguments.requestDispositions.isRequestSuppressed(conversationId, session.requestId);
    if (suppressed) {
        return;
    }
    if (session.assistantTimestamp !== envelope.assistantAtMs) {
        return;
    }
    const previewText = translateChatStreamPreviewKey(envelope.previewKey, envelope.previewArguments);
    if (!previewText) {
        throw new Error('Chat stream status preview event referenced an invalid preview key.');
    }
    if (session.assistantMessage.streamStatusPreviewText === previewText) {
        return;
    }
    applyChatStreamStatusPreview(session.assistantMessage, {
        text: previewText,
        generatedAtMs: envelope.generatedAtMs,
        cooldownMs: envelope.previewCooldownMs,
        trigger: envelope.trigger
    });
    inputArguments.runtime.notify(session, { type: 'timeline-event' });
};

export { dispatchChatStreamStatusPreview };
