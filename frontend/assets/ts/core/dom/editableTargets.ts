/* SoAI - Shared frontend DOM editable targets [frontend/assets/ts/core/dom/editableTargets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const isEditableKeyboardTarget = (target: EventTarget | null): boolean => {
    if (!(target instanceof HTMLElement)) {
        return false;
    }
    return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement || target.isContentEditable;
};

const resolveEditableInteractionElement = (target: EventTarget | null): Element | null => {
    if (target instanceof Element) {
        return target;
    }
    if (target instanceof Node) {
        return target.parentElement;
    }
    return null;
};

const isEditableInteractionTarget = (target: EventTarget | null): boolean => {
    const element = resolveEditableInteractionElement(target);
    if (!element) {
        return false;
    }
    if (element.closest('input, textarea, select, [role="textbox"]') !== null) {
        return true;
    }
    if (element instanceof HTMLElement && element.isContentEditable) {
        return true;
    }
    return element.closest('[contenteditable=""], [contenteditable="true"], [contenteditable="plaintext-only"]') !== null;
};

export { isEditableInteractionTarget, isEditableKeyboardTarget };
