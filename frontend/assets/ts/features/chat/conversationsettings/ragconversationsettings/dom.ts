/* SoAI - Chat feature RAG conversation settings DOM contracts [frontend/assets/ts/features/chat/conversationsettings/ragconversationsettings/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHTMLElement } from '@core/typeGuards.ts';
import { dom } from '@core/dom/dom.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';

interface RagConversationEventCallbacks {
    onConfigInputChange: () => void;
    onConfigInputToggle: (element: Element) => void;
}

const requireRagConversationElement = (modal: Element | null, selector: string): Element => {
    if (!modal) {
        throw new Error('Chat conversation settings require a modal root element');
    }
    const element = dom.resolve(selector, modal);
    if (!element) {
        throw new Error(`Chat conversation settings missing required element ${selector}`);
    }
    return element;
};

const requireRagConversationInput = (modal: Element | null, selector: string): HTMLInputElement => {
    const element = requireRagConversationElement(modal, selector);
    if (!(element instanceof HTMLInputElement)) {
        throw new TypeError(`Chat conversation settings element ${selector} must be an input`);
    }
    return element;
};

const requireRagConversationSelect = (modal: Element | null, selector: string): HTMLSelectElement => {
    const element = requireRagConversationElement(modal, selector);
    if (!(element instanceof HTMLSelectElement)) {
        throw new TypeError(`Chat conversation settings element ${selector} must be a select`);
    }
    return element;
};

const bindRagConversationEvents = (modal: Element, hostOn: ConversationSettingsHost['view']['on'], callbacks: RagConversationEventCallbacks): Array<() => void> => {
    const disposers: Array<() => void> = [];
    const bindAll = (selector: string, eventName: string, handler: (element: Element) => void): void => {
        dom.resolveAll(selector, modal).forEach((element) => {
            if (!isHTMLElement(element)) {
                return;
            }
            disposers.push(hostOn(element, eventName, () => handler(element)));
        });
    };

    bindAll('.rag-config-input', 'input', () => {
        callbacks.onConfigInputChange();
    });

    bindAll('.rag-config-input', 'change', (element) => {
        callbacks.onConfigInputToggle(element);
    });

    return disposers;
};

export type { RagConversationEventCallbacks };
export { bindRagConversationEvents, requireRagConversationElement, requireRagConversationInput, requireRagConversationSelect };
