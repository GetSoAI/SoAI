/* SoAI - Agent mode popup lifecycle for the chat input [frontend/assets/ts/pages/chat/controllers/chatpageagent/agentModePopupController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import { resolveAgentModeLabel } from '@features/chat/public.ts';

const POPUP_VISIBLE_CLASS = 'agent-mode-popup--visible';

interface ActivePopupState {
    element: HTMLElement;
    chatInput: HTMLTextAreaElement;
    focusHandler: () => void;
    blurHandler: () => void;
}

interface AgentModePopupState {
    activePopup: ActivePopupState | null;
}

const createAgentModePopupState = (): AgentModePopupState => ({
    activePopup: null
});

const destroyPopupElement = (state: ActivePopupState): void => {
    state.chatInput.removeEventListener('focus', state.focusHandler);
    state.chatInput.removeEventListener('blur', state.blurHandler);
    state.element.remove();
};

const removeAgentModePopup = (state: AgentModePopupState): void => {
    if (state.activePopup === null) {
        return;
    }
    destroyPopupElement(state.activePopup);
    state.activePopup = null;
};

const createPopupState = (state: AgentModePopupState, chatInput: HTMLTextAreaElement): ActivePopupState => {
    const wrapper = chatInput.parentElement;
    if (!wrapper) {
        throw new Error('Agent mode popup requires a chat input wrapper');
    }

    const popup = chatInput.ownerDocument.createElement('div');
    popup.className = 'agent-mode-popup';
    wrapper.appendChild(popup);

    const focusHandler = (): void => {
        if (state.activePopup?.element === popup) {
            popup.classList.add(POPUP_VISIBLE_CLASS);
        }
    };
    const blurHandler = (): void => {
        if (state.activePopup?.element === popup) {
            popup.classList.remove(POPUP_VISIBLE_CLASS);
        }
    };

    chatInput.addEventListener('focus', focusHandler);
    chatInput.addEventListener('blur', blurHandler);

    return {
        element: popup,
        chatInput,
        focusHandler,
        blurHandler
    };
};

const syncPopupMode = (state: ActivePopupState, mode: AgentMode): void => {
    const popupClassNames = ['agent-mode-popup', `agent-mode-popup--${mode}`];
    if (state.chatInput.ownerDocument.activeElement === state.chatInput) {
        popupClassNames.push(POPUP_VISIBLE_CLASS);
    }
    const nextClassName = popupClassNames.join(' ');
    if (state.element.className !== nextClassName) {
        state.element.className = nextClassName;
    }
    const nextLabel = resolveAgentModeLabel(mode);
    if (state.element.textContent !== nextLabel) {
        state.element.textContent = nextLabel;
    }
};

const showAgentModePopup = (state: AgentModePopupState, chatInput: HTMLTextAreaElement, mode: AgentMode): void => {
    let current = state.activePopup;
    if (current !== null && (current.chatInput !== chatInput || !current.element.isConnected)) {
        destroyPopupElement(current);
        current = null;
        state.activePopup = null;
    }

    if (current === null) {
        const created = createPopupState(state, chatInput);
        current = created;
        state.activePopup = created;
    }

    syncPopupMode(current, mode);
};

const syncAgentModePopupForInput = (state: AgentModePopupState, chatInput: HTMLTextAreaElement | null, mode: AgentMode): void => {
    if (chatInput === null) {
        removeAgentModePopup(state);
        return;
    }
    showAgentModePopup(state, chatInput, mode);
};

export { createAgentModePopupState, removeAgentModePopup, showAgentModePopup, syncAgentModePopupForInput };
export type { AgentModePopupState };
