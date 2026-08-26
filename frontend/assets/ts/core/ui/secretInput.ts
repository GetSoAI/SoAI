/* SoAI - Shared UI secret input [frontend/assets/ts/core/ui/secretInput.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { resolveOptionalKernelService } from '@core/runtime/runtimeContext.ts';
import { replaceChildrenFromTrustedHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const SECRET_INPUT_VISIBLE_CLASS = 'secret-input--visible';
const SECRET_INPUT_TEXT_TYPE = 'text';
const SECRET_INPUT_PASSWORD_TYPE = 'password';
const SECRET_INPUT_CONTAINER_CLASS = 'ui-inline-action-field secret-input-container';
const SECRET_INPUT_TOGGLE_CLASS = 'ui-inline-action-field__button';
const SECRET_INPUT_TOGGLE_ICON_CLASS = 'ui-inline-action-field__icon';
const SECRET_INPUT_TOGGLE_ATTRIBUTE = 'data-secret-input-toggle';
const SECRET_INPUT_TOGGLE_SELECTOR = `[${SECRET_INPUT_TOGGLE_ATTRIBUTE}]`;

const resolveSecretInputType = (): 'password' => {
    return SECRET_INPUT_PASSWORD_TYPE;
};

const isSecretInputVisible = (input: HTMLInputElement): boolean => {
    return input.classList.contains(SECRET_INPUT_VISIBLE_CLASS);
};

const setSecretInputVisibility = (input: HTMLInputElement, visible: boolean): void => {
    input.type = visible ? SECRET_INPUT_TEXT_TYPE : SECRET_INPUT_PASSWORD_TYPE;
    if (visible) {
        input.classList.add(SECRET_INPUT_VISIBLE_CLASS);
        return;
    }
    input.classList.remove(SECRET_INPUT_VISIBLE_CLASS);
};

const resolveSecretInputShowLabel = (): string => i18n.t('common.secretInput.show');

const resolveSecretInputHideLabel = (): string => i18n.t('common.secretInput.hide');

const renderSecretInputToggleIcon = (visible: boolean): string => {
    const iconName = visible ? 'eye-closed' : 'eye-open';
    return getIconSync(iconName, { size: 20 }).html;
};

const renderSecretInputToggle = (inputId: string): string => {
    const label = resolveSecretInputShowLabel();
    return `<button type="button" class="${SECRET_INPUT_TOGGLE_CLASS}" ${SECRET_INPUT_TOGGLE_ATTRIBUTE}="${uiAttr(inputId).html}" aria-label="${uiAttr(label).html}" data-tooltip="${uiAttr(label).html}" aria-pressed="false"><span class="${SECRET_INPUT_TOGGLE_ICON_CLASS}" aria-hidden="true">${renderSecretInputToggleIcon(false)}</span></button>`;
};

const renderSecretInputControl = (options: { inputId: string; inputMarkup: string }): string => {
    return `<div class="${SECRET_INPUT_CONTAINER_CLASS}">${options.inputMarkup}${renderSecretInputToggle(options.inputId)}</div>`;
};

const resolveSecretInputToggle = (event: Event): HTMLButtonElement | null => {
    const target = event.target;
    if (!(target instanceof Element)) {
        return null;
    }
    const element = target.closest(SECRET_INPUT_TOGGLE_SELECTOR);
    if (!element) {
        return null;
    }
    if (!(element instanceof HTMLButtonElement)) {
        throw new TypeError('Secret input toggle must be a button element');
    }
    return element;
};

const requireSecretInputToggleIcon = (button: HTMLButtonElement): HTMLElement => {
    const icon = dom.resolve(`.${SECRET_INPUT_TOGGLE_ICON_CLASS}`, button);
    if (!(icon instanceof HTMLElement)) {
        throw new Error('Secret input toggle icon is missing');
    }
    return icon;
};

const requireSecretInputForToggle = (button: HTMLButtonElement): HTMLInputElement => {
    const inputId = button.getAttribute(SECRET_INPUT_TOGGLE_ATTRIBUTE);
    if (!inputId) {
        throw new Error('Secret input toggle target is missing');
    }
    const input = button.ownerDocument.getElementById(inputId);
    if (!(input instanceof HTMLInputElement)) {
        throw new TypeError('Secret input toggle target must be an input element');
    }
    if (!input.classList.contains('secret-input')) {
        throw new Error('Secret input toggle target must use secret-input');
    }
    return input;
};

const syncSecretInputToggle = (button: HTMLButtonElement, input: HTMLInputElement): void => {
    const visible = isSecretInputVisible(input);
    const label = visible ? resolveSecretInputHideLabel() : resolveSecretInputShowLabel();
    const icon = requireSecretInputToggleIcon(button);
    replaceChildrenFromTrustedHtml({ element: icon, html: getIconSync(visible ? 'eye-closed' : 'eye-open', { size: 20 }) });
    button.setAttribute('aria-label', label);
    button.setAttribute('aria-pressed', visible ? 'true' : 'false');
    setTooltipText(button, label);
};

const toggleSecretInputForButton = (button: HTMLButtonElement): void => {
    const input = requireSecretInputForToggle(button);
    setSecretInputVisibility(input, !isSecretInputVisible(input));
    syncSecretInputToggle(button, input);
};

interface SecretInputToggleService {
    initialize: () => void;
    destroy: () => void;
}

class SecretInputToggleController implements SecretInputToggleService {
    readonly #documentRef: Document;
    #abortController: AbortController | null = null;

    constructor(dependencies: { documentRef: Document }) {
        this.#documentRef = dependencies.documentRef;
    }

    initialize(): void {
        if (this.#abortController) {
            return;
        }
        const abortController = new AbortController();
        this.#documentRef.addEventListener('click', this.#handleClick, { signal: abortController.signal, capture: true });
        this.#abortController = abortController;
    }

    destroy(): void {
        this.#abortController?.abort('secret-input-toggle-destroyed');
        this.#abortController = null;
    }

    readonly #handleClick = (event: Event): void => {
        if (event instanceof MouseEvent && event.button !== 0) {
            return;
        }
        const button = resolveSecretInputToggle(event);
        if (!button) {
            return;
        }
        event.preventDefault();
        toggleSecretInputForButton(button);
    };
}

const createSecretInputToggleService = (dependencies: { documentRef: Document }): SecretInputToggleService => new SecretInputToggleController(dependencies);

const resetSecretInputToggleService = (): void => {
    const candidate = resolveOptionalKernelService('core.secretInputToggle');
    if (candidate && 'destroy' in candidate && typeof candidate.destroy === 'function') {
        candidate.destroy();
    }
};

export { SECRET_INPUT_PASSWORD_TYPE, SECRET_INPUT_TEXT_TYPE, SECRET_INPUT_VISIBLE_CLASS, createSecretInputToggleService, isSecretInputVisible, renderSecretInputControl, resetSecretInputToggleService, resolveSecretInputType, setSecretInputVisibility };
export type { SecretInputToggleService };
