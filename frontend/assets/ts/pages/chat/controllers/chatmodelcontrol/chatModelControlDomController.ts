/* SoAI - Chat page model control DOM controller [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/chatModelControlDomController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import type { ModelControlScope } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlWidget.ts';

export const CHAT_MODEL_CONTROL_ROOT_SELECTOR = '[data-chat-model-control="true"]';
export const CHAT_MODEL_CONTROL_SELECTOR = '.chat-model-control';
export const CHAT_MODEL_MENU_SELECTOR = '.chat-model-menu';
export const CHAT_MODEL_OPEN_MENU_SELECTOR = '.chat-model-menu.is-open';
export const CHAT_MODEL_OPEN_TRIGGER_SELECTOR = '.chat-model-control-primary.is-open, .chat-model-slot.is-open';

export const requireChatModelControlScopeFromRoot = (root: Element): ModelControlScope => {
    const scopeValue = root.getAttribute('data-scope');
    if (scopeValue === 'sidebar' || scopeValue === 'composer' || scopeValue === 'empty-state' || scopeValue === 'configuration') {
        return scopeValue;
    }
    throw new Error('Chat model control root requires a valid data-scope');
};

export const resolveClosestChatModelControlRoot = (actionElement: HTMLElement): HTMLElement | null => {
    const root = actionElement.closest(CHAT_MODEL_CONTROL_ROOT_SELECTOR);
    return root instanceof HTMLElement ? root : null;
};

export const parseChatModelControlSlotIndex = (actionElement: HTMLElement): number => {
    return requireNonNegativeIntegerAttribute(actionElement, 'data-slot-index', 'Chat model control slot index');
};
