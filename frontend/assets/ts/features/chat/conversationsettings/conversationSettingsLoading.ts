/* SoAI - Chat feature conversation settings loading [frontend/assets/ts/features/chat/conversationsettings/conversationSettingsLoading.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { isInstanceOf } from '@core/typeGuards.ts';
import { setAriaBusy } from '@core/ui/controls/ariaBusy.ts';
import { createBusyDisabledToken, getBusyDisabledToken, setBusyDisabledState, type BusyDisabledTarget } from '@core/ui/controls/busyDisabledState.ts';

const SECTION_LOADING_TOKEN_ATTR = 'data-chat-settings-loading-token';
const HYDRATION_TOKEN_ATTR = 'data-chat-settings-hydration-token';
const HYDRATION_CONTROL_TOKEN_ATTR = 'data-chat-settings-hydration-control-token';
const HYDRATION_SCOPE_ATTR = 'data-chat-settings-hydration-scope';
const HYDRATION_OVERLAY_CLASS = 'chat-settings-hydration-overlay';

interface ConversationSettingsHydrationSession {
    releaseControlsBeforeRender(): void;
    finish(): void;
    cancel(): void;
}

interface ConversationSettingsHydrationTargets {
    containers: readonly Element[];
}

const setSectionLoading = (inputArguments: { container: Element; loading: boolean }): void => {
    const container = inputArguments.container;
    setAriaBusy(container, inputArguments.loading);

    const controls = Array.from(dom.resolveAll('input, select, textarea, button', container));
    controls.forEach((node) => {
        const isControl = isInstanceOf(node, HTMLInputElement) || isInstanceOf(node, HTMLSelectElement) || isInstanceOf(node, HTMLTextAreaElement) || isInstanceOf(node, HTMLButtonElement);
        if (!isControl) {
            throw new TypeError('Conversation settings loading selector returned unexpected element');
        }
        if (node.classList.contains('chat-configuration-save-btn')) {
            return;
        }

        if (inputArguments.loading) {
            if (getBusyDisabledToken(node) !== null) {
                return;
            }
            const token = setBusyDisabledState(node, { isBusy: true, createToken: createBusyDisabledToken, spinner: 'none' });
            node.setAttribute(SECTION_LOADING_TOKEN_ATTR, token);
            return;
        }

        const token = node.getAttribute(SECTION_LOADING_TOKEN_ATTR);
        if (!token) {
            return;
        }
        setBusyDisabledState(node, { isBusy: false, token });
        node.removeAttribute(SECTION_LOADING_TOKEN_ATTR);
    });
};

const setMcpLoading = (inputArguments: { container: Element; defaultToolsModalBody: Element; emptyState: Element | null; loading: boolean }): void => {
    setSectionLoading({ container: inputArguments.container, loading: inputArguments.loading });
    setSectionLoading({ container: inputArguments.defaultToolsModalBody, loading: inputArguments.loading });
    if (inputArguments.emptyState && inputArguments.loading) {
        inputArguments.emptyState.textContent = i18n.t('common.loading');
        inputArguments.emptyState.classList.remove('u-hidden');
    }
};

const isBusyDisabledTarget = (node: Element): node is BusyDisabledTarget => {
    return isInstanceOf(node, HTMLInputElement) || isInstanceOf(node, HTMLSelectElement) || isInstanceOf(node, HTMLTextAreaElement) || isInstanceOf(node, HTMLButtonElement) || isInstanceOf(node, HTMLAnchorElement);
};

const queryHydrationControls = (container: Element): BusyDisabledTarget[] => {
    return Array.from(dom.resolveAll('input, select, textarea, button, a', container)).map((node) => {
        if (!isBusyDisabledTarget(node)) {
            throw new TypeError('Conversation settings hydration selector returned unexpected element');
        }
        return node;
    });
};

const createHydrationOverlay = (token: string): HTMLElement => {
    const overlay = dom.create('div', {
        class: `modal-loading-state modal-loading-state--overlay ${HYDRATION_OVERLAY_CLASS}`,
        'aria-live': 'polite'
    });
    overlay.setAttribute(HYDRATION_TOKEN_ATTR, token);
    const spinner = dom.create('span', { class: 'loading-spinner', 'aria-hidden': 'true' });
    const text = dom.create('span', { class: 'loading-text' });
    text.textContent = i18n.t('common.loading');
    overlay.appendChild(spinner);
    overlay.appendChild(text);
    return overlay;
};

const removeHydrationOverlay = (container: Element, token: string | null): void => {
    const overlays = Array.from(dom.resolveAll(`.${HYDRATION_OVERLAY_CLASS}`, container));
    for (const overlay of overlays) {
        if (token !== null && overlay.getAttribute(HYDRATION_TOKEN_ATTR) !== token) {
            continue;
        }
        overlay.remove();
    }
};

const releaseHydrationControls = (containers: readonly Element[], token: string | null): void => {
    for (const container of containers) {
        for (const control of queryHydrationControls(container)) {
            const controlToken = control.getAttribute(HYDRATION_CONTROL_TOKEN_ATTR);
            if (!controlToken || (token !== null && controlToken !== token)) {
                continue;
            }
            setBusyDisabledState(control, { isBusy: false, token: controlToken });
            control.removeAttribute(HYDRATION_CONTROL_TOKEN_ATTR);
        }
    }
};

const clearHydrationContainer = (container: Element): void => {
    releaseHydrationControls([container], null);
    removeHydrationOverlay(container, null);
    container.removeAttribute(HYDRATION_TOKEN_ATTR);
    container.removeAttribute(HYDRATION_SCOPE_ATTR);
    setAriaBusy(container, false);
};

const collectHydrationContainers = (containers: readonly Element[]): Element[] => {
    const hydrationContainers: Element[] = [];
    for (const container of containers) {
        if (container.getAttribute(HYDRATION_SCOPE_ATTR) === 'true' && !hydrationContainers.includes(container)) {
            hydrationContainers.push(container);
        }
        for (const descendant of dom.resolveAll(`[${HYDRATION_SCOPE_ATTR}='true']`, container)) {
            if (!hydrationContainers.includes(descendant)) {
                hydrationContainers.push(descendant);
            }
        }
    }
    return hydrationContainers;
};

const clearConversationSettingsHydration = (targets: ConversationSettingsHydrationTargets): void => {
    for (const container of collectHydrationContainers(targets.containers)) {
        clearHydrationContainer(container);
    }
};

const beginConversationSettingsHydration = (targets: ConversationSettingsHydrationTargets): ConversationSettingsHydrationSession => {
    const token = createBusyDisabledToken();
    clearConversationSettingsHydration(targets);
    for (const container of targets.containers) {
        container.setAttribute(HYDRATION_TOKEN_ATTR, token);
        container.setAttribute(HYDRATION_SCOPE_ATTR, 'true');
        setAriaBusy(container, true);
        container.appendChild(createHydrationOverlay(token));
        for (const control of queryHydrationControls(container)) {
            if (control.classList.contains('chat-configuration-save-btn') || getBusyDisabledToken(control) !== null) {
                continue;
            }
            setBusyDisabledState(control, { isBusy: true, createToken: () => token, spinner: 'none' });
            control.setAttribute(HYDRATION_CONTROL_TOKEN_ATTR, token);
        }
    }
    const finishSession = (): void => {
        releaseHydrationControls(targets.containers, token);
        for (const container of targets.containers) {
            if (container.getAttribute(HYDRATION_TOKEN_ATTR) !== token) {
                continue;
            }
            removeHydrationOverlay(container, token);
            container.removeAttribute(HYDRATION_TOKEN_ATTR);
            container.removeAttribute(HYDRATION_SCOPE_ATTR);
            setAriaBusy(container, false);
        }
    };
    return {
        releaseControlsBeforeRender: (): void => {
            releaseHydrationControls(targets.containers, token);
        },
        finish: finishSession,
        cancel: finishSession
    };
};

export { beginConversationSettingsHydration, clearConversationSettingsHydration, setMcpLoading, setSectionLoading };
export type { ConversationSettingsHydrationSession, ConversationSettingsHydrationTargets };
