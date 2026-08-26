/* SoAI - Chat feature secret prompt DOM contracts [frontend/assets/ts/features/chat/secretprompt/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';

const SECRET_PROMPT_ROOT_SELECTOR = '.secret-prompt-root';
const SECRET_PROMPT_INPUT_SELECTOR = '.secret-prompt-input';
const SECRET_PROMPT_SAVE_CHECKBOX_SELECTOR = '.secret-prompt-save-checkbox';

const optionalSecretPromptRootFromChild = (element: Element | null): HTMLElement | null => {
    const candidate = element instanceof Element ? element : null;
    if (!candidate) {
        return null;
    }
    const root = candidate.closest(SECRET_PROMPT_ROOT_SELECTOR);
    return root instanceof HTMLElement ? root : null;
};

const optionalSecretPromptInput = (root: Element | null, fieldId: string): HTMLInputElement | null => {
    if (!root || !(root instanceof Element)) {
        return null;
    }
    const selector = `${SECRET_PROMPT_INPUT_SELECTOR}[data-field-id="${CSS.escape(fieldId)}"]`;
    const candidate = dom.resolve(selector, root);
    return candidate instanceof HTMLInputElement ? candidate : null;
};

const optionalSecretPromptSaveCheckbox = (root: Element | null): HTMLInputElement | null => {
    if (!root || !(root instanceof Element)) {
        return null;
    }
    const candidate = dom.resolve(SECRET_PROMPT_SAVE_CHECKBOX_SELECTOR, root);
    return candidate instanceof HTMLInputElement ? candidate : null;
};

const optionalSecretPromptLabelWrapper = (root: Element | null): HTMLElement | null => {
    if (!root || !(root instanceof Element)) {
        return null;
    }
    const candidate = dom.resolve('[data-field-id="label_wrapper"]', root);
    return candidate instanceof HTMLElement ? candidate : null;
};

const setSecretPromptLabelVisibility = (root: Element | null, visible: boolean): void => {
    const wrapper = optionalSecretPromptLabelWrapper(root);
    if (!wrapper) {
        return;
    }
    wrapper.classList.toggle(CSS_CLASSES.HIDDEN, !visible);
    wrapper.setAttribute('aria-hidden', visible ? 'false' : 'true');
};

const focusSecretPrompt = (root: Element | null): void => {
    if (!(root instanceof HTMLElement)) {
        return;
    }
    const passwordInput = dom.resolve(`${SECRET_PROMPT_INPUT_SELECTOR}.secret-input`, root);
    if (passwordInput instanceof HTMLInputElement && !passwordInput.disabled && !passwordInput.value.trim()) {
        passwordInput.focus({ preventScroll: true });
        return;
    }
    const requiredInput = dom.resolve(`${SECRET_PROMPT_INPUT_SELECTOR}[required]`, root);
    if (requiredInput instanceof HTMLInputElement && !requiredInput.disabled && !requiredInput.value.trim()) {
        requiredInput.focus({ preventScroll: true });
        return;
    }
    const firstInput = dom.resolve(SECRET_PROMPT_INPUT_SELECTOR, root);
    if (firstInput instanceof HTMLInputElement && !firstInput.disabled) {
        firstInput.focus({ preventScroll: true });
    }
};

export { focusSecretPrompt, optionalSecretPromptInput, optionalSecretPromptRootFromChild, optionalSecretPromptSaveCheckbox, setSecretPromptLabelVisibility };
