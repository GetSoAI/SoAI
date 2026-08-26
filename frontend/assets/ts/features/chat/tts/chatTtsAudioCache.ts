/* SoAI - Chat TTS audio cache [frontend/assets/ts/features/chat/tts/chatTtsAudioCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpenAiSpeechPayload } from '@features/chat/tts/chatTtsOpenAiAudio.ts';

interface PreparedChatTtsAudio {
    readonly url: string;
    release(): void;
}

interface ChatTtsAudioCacheEntry {
    url: string;
    retainCount: number;
}

class ChatTtsAudioCache {
    readonly #entries = new Map<string, ChatTtsAudioCacheEntry>();
    readonly #limit: number;

    constructor(limit: number) {
        this.#limit = limit;
    }

    retain(payload: OpenAiSpeechPayload): PreparedChatTtsAudio | null {
        const key = this.#buildKey(payload);
        const entry = this.#entries.get(key);
        if (!entry) {
            return null;
        }
        this.#entries.delete(key);
        this.#entries.set(key, entry);
        return this.#retainEntry(entry);
    }

    storeAndRetain(payload: OpenAiSpeechPayload, url: string): PreparedChatTtsAudio {
        const key = this.#buildKey(payload);
        const previous = this.#entries.get(key);
        if (previous) {
            URL.revokeObjectURL(url);
            this.#entries.delete(key);
            this.#entries.set(key, previous);
            return this.#retainEntry(previous);
        }
        const entry: ChatTtsAudioCacheEntry = { url, retainCount: 0 };
        this.#entries.set(key, entry);
        this.#evictIfNeeded();
        return this.#retainEntry(entry);
    }

    dispose(): void {
        for (const entry of this.#entries.values()) {
            URL.revokeObjectURL(entry.url);
        }
        this.#entries.clear();
    }

    #buildKey(payload: OpenAiSpeechPayload): string {
        return JSON.stringify(payload);
    }

    #retainEntry(entry: ChatTtsAudioCacheEntry): PreparedChatTtsAudio {
        entry.retainCount += 1;
        let released = false;
        return {
            url: entry.url,
            release: () => {
                if (released) {
                    return;
                }
                released = true;
                entry.retainCount = Math.max(0, entry.retainCount - 1);
                this.#evictIfNeeded();
            }
        };
    }

    #evictIfNeeded(): void {
        while (this.#entries.size > this.#limit) {
            const removableKey = this.#oldestRemovableKey();
            if (removableKey === null) {
                return;
            }
            const entry = this.#entries.get(removableKey);
            this.#entries.delete(removableKey);
            if (entry) {
                URL.revokeObjectURL(entry.url);
            }
        }
    }

    #oldestRemovableKey(): string | null {
        for (const [key, entry] of this.#entries.entries()) {
            if (entry.retainCount === 0) {
                return key;
            }
        }
        return null;
    }
}

export { ChatTtsAudioCache };
export type { PreparedChatTtsAudio };
