/* SoAI - Chat page element access and composer control state [frontend/assets/ts/pages/chat/controllers/chatpage/presentation/ChatPageElementsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAll } from '@core/dom/dom.ts';
import { isInstanceOf } from '@core/typeGuards.ts';
import { CHAT_SELECTORS, type AudioState, type ChatParameters } from '@features/chat/public.ts';
import { updateMicrophoneButtonState } from '@pages/chat/controllers/page/dom/audio.ts';
import { updateCallButtonState } from '@pages/chat/controllers/page/dom/call.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ChatPageElementsDependencies extends PageDomOwnerHost {
    setUIValue(target: string | Element, value: string | null, options?: { attribute?: string }): void;
    getDocument(): Document;
    getParameters(): ChatParameters;
    getMicrophoneAudioState(): AudioState;
    setMicrophoneAudioState(state: AudioState): void;
}

class ChatPageElementsManager {
    readonly #dependencies: ChatPageElementsDependencies;

    constructor(dependencies: ChatPageElementsDependencies) {
        this.#dependencies = dependencies;
    }

    updateMicrophoneButtonState(state: AudioState): void {
        const previousState = this.#dependencies.getMicrophoneAudioState();
        this.#dependencies.setMicrophoneAudioState(state);
        updateMicrophoneButtonState(this.#dependencies, state, {
            previousState,
            soundEffectsEnabled: this.#dependencies.getParameters().microphoneSoundEffectsEnabled !== false
        });
    }

    updateCallButtonState(active: boolean): void {
        updateCallButtonState(this.#dependencies, active);
    }

    getChatInputElement(): HTMLTextAreaElement | null {
        const element = this.#dependencies.pageDom.optional(CHAT_SELECTORS.INPUT);
        return isInstanceOf(element, HTMLTextAreaElement) ? element : null;
    }

    getConversationTitleElement(): HTMLElement | null {
        const element = this.#dependencies.pageDom.optional(CHAT_SELECTORS.CONVERSATION_TITLE);
        return isInstanceOf(element, HTMLElement) ? element : null;
    }

    getConversationTitleInputElement(): HTMLInputElement | null {
        const element = this.#dependencies.pageDom.optional(CHAT_SELECTORS.CONVERSATION_TITLE_INPUT);
        return isInstanceOf(element, HTMLInputElement) ? element : null;
    }

    getConversationListTitleInputElement(): HTMLInputElement | null {
        const element = this.#dependencies.pageDom.optional(CHAT_SELECTORS.CONVERSATION_LIST_TITLE_INPUT);
        return isInstanceOf(element, HTMLInputElement) ? element : null;
    }

    queryDocumentUI(selector: string): Element[] {
        return resolveAll(selector, this.#dependencies.getDocument());
    }

    requireTokenCounterButtons(): HTMLButtonElement[] {
        const buttons: HTMLButtonElement[] = [];
        for (const element of this.#dependencies.pageDom.query(CHAT_SELECTORS.TOKEN_COUNTER_BTN)) {
            if (element instanceof HTMLButtonElement) {
                buttons.push(element);
            }
        }
        if (buttons.length === 0) {
            throw new Error('Chat token counter buttons are not available');
        }
        return buttons;
    }
}

export { ChatPageElementsManager };
export type { ChatPageElementsDependencies };
export interface ChatPageElementsHost {
    elements: ChatPageElementsManager;
}
