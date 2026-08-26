/* SoAI - Chat parameter send toggle UI effects [frontend/assets/ts/core/chat/parameters/parameterSendToggleEffects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_PARAMETER_SEND_CONTROLS, CHAT_PARAMETER_WIRE_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import { dom } from '@core/dom/dom.ts';
import type { ChatParameters } from '@core/chat/parameters/types.ts';
import { setControlDisabledState, type DisableableControl } from '@core/ui/controls/disabledState.ts';

const isDisableableControl = (element: Element): element is DisableableControl => element instanceof HTMLButtonElement || element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement;

const applyDisplayDisabledState = (root: Document | Element | DocumentFragment, element: Element, disabled: boolean): void => {
    const displaySelector = element.getAttribute('data-display');
    if (!displaySelector) {
        return;
    }
    const displayElement = dom.resolve(displaySelector, root);
    if (!displayElement) {
        return;
    }
    displayElement.setAttribute('aria-disabled', disabled ? 'true' : 'false');
    if (displayElement.closest('.chat-config-field-header > label')) {
        displayElement.classList.remove('chat-config-field-display-disabled');
        return;
    }
    displayElement.classList.toggle('chat-config-field-display-disabled', disabled);
};

const applyLabelDisabledState = (element: Element, disabled: boolean): void => {
    const field = element.closest('.form-group');
    const label = field ? dom.resolve('.chat-config-field-header > label', field) : null;
    if (!label) {
        return;
    }
    label.setAttribute('aria-disabled', disabled ? 'true' : 'false');
    label.classList.toggle('chat-config-field-display-disabled', disabled);
};

const applyParameterSendEnabledStates = (root: Document | Element | DocumentFragment, parameters: ChatParameters): void => {
    for (const control of CHAT_PARAMETER_SEND_CONTROLS) {
        const disabled = parameters[control.flag] === false;
        const domParameter = CHAT_PARAMETER_WIRE_KEYS[control.parameter] ?? control.parameter;
        const elements = dom.resolveAll(`[data-param="${domParameter}"]`, root);
        for (const element of elements) {
            if (isDisableableControl(element)) {
                setControlDisabledState(element, disabled);
            }
            applyDisplayDisabledState(root, element, disabled);
            applyLabelDisabledState(element, disabled);
        }
    }
};

export { applyParameterSendEnabledStates };
