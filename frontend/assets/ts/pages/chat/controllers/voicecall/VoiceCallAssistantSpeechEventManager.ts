/* SoAI - Voice call assistant speech event ownership [frontend/assets/ts/pages/chat/controllers/voicecall/VoiceCallAssistantSpeechEventManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface VoiceCallAssistantSpeechListener {
    speechStateChanged(speaking: boolean): void;
    speechQueueDrained(): void;
    playbackFailed(): void;
}

class VoiceCallAssistantSpeechEventManager {
    readonly #listeners = new Set<VoiceCallAssistantSpeechListener>();

    subscribe(listener: VoiceCallAssistantSpeechListener): () => void {
        this.#listeners.add(listener);
        return () => this.#listeners.delete(listener);
    }

    speechStateChanged(speaking: boolean): void {
        for (const listener of this.#listeners) listener.speechStateChanged(speaking);
    }

    speechQueueDrained(): void {
        for (const listener of this.#listeners) listener.speechQueueDrained();
    }

    playbackFailed(): void {
        for (const listener of this.#listeners) listener.playbackFailed();
    }

    clear(): void {
        this.#listeners.clear();
    }
}

export { VoiceCallAssistantSpeechEventManager };
export type { VoiceCallAssistantSpeechListener };
