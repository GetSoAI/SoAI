/* SoAI - Voice call assistant speech cursor controller [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallAssistantSpeechCursorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ChatMessage, MessageSegment, StreamUpdate } from '@features/chat/public.ts';
import { resolveTextOnly } from '@pages/chat/controllers/voicecall/mappers.ts';

interface VoiceCallAssistantSpeechCursorControllerHost {
    resolveMessageContentSegments(message: ChatMessage): MessageSegment[];
    resolveAssistantSpeechText(segments: MessageSegment[]): string;
}

interface VoiceCallAssistantSpeechDelta {
    requestKey: string;
    text: string;
}

class VoiceCallAssistantSpeechCursorController {
    readonly #host: VoiceCallAssistantSpeechCursorControllerHost;
    #requestKey: string | null = null;
    #sourceText = '';
    #spokenText = '';
    #streamingConsumed = false;

    constructor(host: VoiceCallAssistantSpeechCursorControllerHost) {
        this.#host = host;
    }

    reset(): void {
        this.#requestKey = null;
        this.#sourceText = '';
        this.#spokenText = '';
        this.#streamingConsumed = false;
    }

    beginRequest(requestKey: string): void {
        if (this.#requestKey === requestKey) {
            return;
        }
        this.#requestKey = requestKey;
        this.#sourceText = '';
        this.#spokenText = '';
        this.#streamingConsumed = false;
    }

    resolveDelta(update: StreamUpdate): VoiceCallAssistantSpeechDelta | null {
        const requestKey = buildVoiceCallSpeechRequestKey(update.conversationId, update.requestId, update.assistantTimestamp);
        this.beginRequest(requestKey);
        if (update.mutation.type === 'text-delta' && isString(update.mutation.textDelta)) {
            return this.#resolveStreamingDelta(requestKey, update.mutation.textDelta);
        }
        return this.#resolveTerminalSuffix(requestKey, update.message);
    }

    #resolveStreamingDelta(requestKey: string, sourceDelta: string): VoiceCallAssistantSpeechDelta | null {
        if (!sourceDelta) {
            return null;
        }
        this.#sourceText = `${this.#sourceText}${sourceDelta}`;
        const sourceSegment: MessageSegment = { type: 'text', text: this.#sourceText, value: this.#sourceText };
        const nextSpeechText = this.#host.resolveAssistantSpeechText([sourceSegment]);
        const suffix = resolveStrictSpeechSuffix(this.#spokenText, nextSpeechText);
        this.#spokenText = nextSpeechText;
        this.#streamingConsumed = true;
        return suffix ? { requestKey, text: suffix } : null;
    }

    #resolveTerminalSuffix(requestKey: string, message: ChatMessage): VoiceCallAssistantSpeechDelta | null {
        const segments = this.#host.resolveMessageContentSegments(message);
        this.#sourceText = resolveTextOnly(segments);
        const nextSpeechText = this.#host.resolveAssistantSpeechText(segments);
        const suffix = resolveStrictSpeechSuffix(this.#spokenText, nextSpeechText);
        if (!suffix) {
            this.#spokenText = nextSpeechText;
            return null;
        }
        if (this.#streamingConsumed && !nextSpeechText.startsWith(this.#spokenText)) {
            this.#spokenText = nextSpeechText;
            return null;
        }
        this.#spokenText = nextSpeechText;
        return { requestKey, text: suffix };
    }
}

const buildVoiceCallSpeechRequestKey = (conversationId: string, requestId: string, assistantTimestamp: number): string => {
    return `${conversationId}\n${requestId}\n${assistantTimestamp}`;
};

const resolveStrictSpeechSuffix = (previousText: string, nextText: string): string => {
    if (!nextText) {
        return '';
    }
    if (!previousText) {
        return nextText;
    }
    if (nextText.startsWith(previousText)) {
        return nextText.slice(previousText.length);
    }
    return '';
};

export { VoiceCallAssistantSpeechCursorController, buildVoiceCallSpeechRequestKey, resolveStrictSpeechSuffix };
export type { VoiceCallAssistantSpeechDelta };
