/* SoAI - Chat elicitation preview DOM ownership [frontend/assets/ts/features/chat/elicitation/ChatElicitationPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import type { ElicitationType } from '@features/chat/elicitation/ChatElicitationSession.ts';

interface ChatElicitationPreviewDependencies {
    optionalUI(selector: string, context?: Element): Element | null;
    queryUI(selector: string, context?: Element): Element[];
    updateHtml(element: Element, markup: TrustedHtml | string): void;
    toggleClass(element: Element, className: string, add: boolean): void;
    updateAttribute(element: Element, attribute: string, value: string | null): void;
}

const ELICITATION_SELECTORS: Record<ElicitationType, string> = {
    askUser: CHAT_SELECTORS.ASK_USER_PREVIEW,
    secretPrompt: CHAT_SELECTORS.SECRET_PROMPT_PREVIEW,
    toolApproval: CHAT_SELECTORS.TOOL_APPROVAL_PREVIEW
};

class ChatElicitationPreview {
    readonly #dependencies: ChatElicitationPreviewDependencies;

    constructor(dependencies: ChatElicitationPreviewDependencies) {
        this.#dependencies = dependencies;
    }

    update(type: ElicitationType, markup: TrustedHtml | null): void {
        const target = this.#dependencies.optionalUI(ELICITATION_SELECTORS[type]);
        if (target instanceof HTMLElement) {
            this.#dependencies.updateHtml(target, markup ?? '');
            const visible = Boolean(markup?.html.trim());
            this.#dependencies.toggleClass(target, CSS_CLASSES.HIDDEN, !visible);
            this.#dependencies.updateAttribute(target, 'aria-hidden', visible ? 'false' : 'true');
        }
        const previewsContainer = this.#dependencies.optionalUI('.chat-previews-container');
        if (previewsContainer instanceof HTMLElement) previewsContainer.scrollTop = 0;
        this.#syncLayout();
    }

    #syncLayout(): void {
        const container = this.#dependencies.optionalUI('.chat-previews-container');
        if (!(container instanceof HTMLElement)) return;
        const visible = (selector: string): boolean => {
            const element = this.#dependencies.optionalUI(selector);
            return element instanceof HTMLElement && !element.classList.contains(CSS_CLASSES.HIDDEN);
        };
        const requiresInput = visible(CHAT_SELECTORS.TOOL_APPROVAL_PREVIEW) || visible(CHAT_SELECTORS.ASK_USER_PREVIEW) || visible(CHAT_SELECTORS.SECRET_PROMPT_PREVIEW);
        const eitherVisible = requiresInput || visible(CHAT_SELECTORS.PREVIEW) || visible(CHAT_SELECTORS.INPUT_QUEUE_PREVIEW) || visible(CHAT_SELECTORS.VOICE_RECORDING_PREVIEW);
        const messages = this.#dependencies.optionalUI(CHAT_SELECTORS.MESSAGES_CONTAINER);
        if (messages instanceof HTMLElement) {
            this.#dependencies.updateAttribute(messages, 'data-user-input-required', requiresInput ? 'true' : null);
            const actions = this.#dependencies.queryUI('.chat-message.assistant .message-content.message-content--with-header > .message-actions', messages);
            for (const action of actions) this.#dependencies.updateAttribute(action, 'data-user-input-required', null);
            const lastAction = actions[actions.length - 1];
            if (requiresInput && lastAction) this.#dependencies.updateAttribute(lastAction, 'data-user-input-required', 'true');
        }
        this.#dependencies.toggleClass(container, CSS_CLASSES.HIDDEN, !eitherVisible);
    }
}

export { ChatElicitationPreview };
export type { ChatElicitationPreviewDependencies };
