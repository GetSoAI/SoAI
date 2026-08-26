/* SoAI - Chat feature speak action controller [frontend/assets/ts/features/chat/message/speakActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { extractSpeechTextFromHtml, setSpeakButtonLoading, setSpeakButtonMode } from '@features/chat/message/messageSpeech.ts';
import { serializeElementChildrenToHtml } from '@core/dom/html.ts';

interface SpeakActionControllerDependencies {
    resolveMessageContainer: (messageId: string) => HTMLElement | null;
    speakText: (text: string, options?: { onPlaybackStart?: (() => void) | null }) => Promise<void>;
    stopSpeaking: () => void;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    showNotification: (message: string, type: 'error' | 'warning' | 'success' | 'info') => void;
}

type SpeakState = 'idle' | 'loading' | 'playing';

class SpeakActionController {
    readonly #dependencies: SpeakActionControllerDependencies;
    #state: SpeakState;
    #activeMessageId: string | null;
    #activeButton: HTMLButtonElement | null;
    #activeOperationId: number;
    #activeLoadingToken: string | null;

    constructor(dependencies: SpeakActionControllerDependencies) {
        this.#dependencies = dependencies;
        this.#state = 'idle';
        this.#activeMessageId = null;
        this.#activeButton = null;
        this.#activeOperationId = 0;
        this.#activeLoadingToken = null;
    }

    dispose(): void {
        if (this.#state === 'idle') {
            return;
        }
        this.#interruptActiveSpeak();
    }

    async handleSpeakAction(messageId: string): Promise<void> {
        if (this.#state !== 'idle') {
            if (this.#activeMessageId === messageId) {
                this.#interruptActiveSpeak();
                return;
            }
            this.#interruptActiveSpeak();
        }
        await this.#startSpeak(messageId);
    }

    async #startSpeak(messageId: string): Promise<void> {
        const operationId = this.#activeOperationId + 1;
        this.#activeOperationId = operationId;
        try {
            const container = this.#dependencies.resolveMessageContainer(messageId);
            if (!container) {
                throw new Error('Cannot speak message: message container was not found');
            }
            const messageTextNode = dom.resolve('.message-text', container);
            if (!(messageTextNode instanceof HTMLElement)) {
                throw new Error('Cannot speak message: message text node was not found');
            }
            const button = dom.resolve('.speak-message-btn', container);
            if (!(button instanceof HTMLButtonElement)) {
                throw new Error('Cannot speak message: speak button was not found');
            }
            setSpeakButtonMode(button, 'speak');
            const text = extractSpeechTextFromHtml(serializeElementChildrenToHtml(messageTextNode));
            if (!text) {
                this.#dependencies.showNotification(i18n.t('chat.message.speak.noText'), 'warning');
                return;
            }

            this.#state = 'loading';
            this.#activeMessageId = messageId;
            this.#activeButton = button;
            this.#activeLoadingToken = setSpeakButtonLoading(button, true);
            await this.#dependencies.runWithBoundary('chat:speakMessage', async () => {
                await this.#dependencies.speakText(text, {
                    onPlaybackStart: () => {
                        if (this.#activeOperationId !== operationId || this.#state !== 'loading') {
                            return;
                        }
                        if (!this.#activeLoadingToken || !this.#activeButton) {
                            throw new Error('Speak playback state is inconsistent');
                        }
                        setSpeakButtonLoading(this.#activeButton, false, this.#activeLoadingToken);
                        this.#activeLoadingToken = null;
                        setSpeakButtonMode(this.#activeButton, 'stop');
                        this.#state = 'playing';
                    }
                });
            });
        } catch {
            this.#dependencies.showNotification(i18n.t('chat.message.speak.failed'), 'error');
        } finally {
            if (this.#activeOperationId !== operationId) {
                return;
            }
            this.#resetActiveSpeakState();
        }
    }

    #interruptActiveSpeak(): void {
        this.#activeOperationId += 1;
        this.#dependencies.stopSpeaking();
        this.#resetActiveSpeakState();
    }

    #resetActiveSpeakState(): void {
        if (this.#activeButton) {
            if (this.#activeLoadingToken) {
                setSpeakButtonLoading(this.#activeButton, false, this.#activeLoadingToken);
            }
            setSpeakButtonMode(this.#activeButton, 'speak');
        }
        this.#activeLoadingToken = null;
        this.#state = 'idle';
        this.#activeMessageId = null;
        this.#activeButton = null;
    }
}

export { SpeakActionController };
export type { SpeakActionControllerDependencies };
