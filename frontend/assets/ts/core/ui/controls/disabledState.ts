/* SoAI - Shared UI disabled state [frontend/assets/ts/core/ui/controls/disabledState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type DisableableControl = HTMLButtonElement | HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

const setControlDisabledState = (element: DisableableControl, disabled: boolean): void => {
    element.disabled = disabled;
    element.setAttribute('aria-disabled', disabled ? 'true' : 'false');
    if (disabled) {
        element.setAttribute('tabindex', '-1');
        return;
    }
    element.removeAttribute('tabindex');
};

const setControlDisabledStateForEach = (elements: readonly DisableableControl[], disabled: boolean): void => {
    for (const element of elements) {
        setControlDisabledState(element, disabled);
    }
};

const renderControlDisabledAttributes = (disabled: boolean): string => (disabled ? ' disabled aria-disabled="true" tabindex="-1"' : ' aria-disabled="false"');

export { renderControlDisabledAttributes, setControlDisabledState, setControlDisabledStateForEach };
export type { DisableableControl };
