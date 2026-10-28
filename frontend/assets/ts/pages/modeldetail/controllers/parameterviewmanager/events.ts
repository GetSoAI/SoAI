/* SoAI - Model detail page control layer parameter view manager events [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setControlValidity } from '@core/dom/formValidity.ts';
import { updateToggleLabel } from '@core/toggleSwitch.ts';
import type { ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { getDomData, registerHandlers } from '@pages/modeldetail/controllers/parameterviewmanager/dom.ts';
import type { BoundParameterEvents, ParameterViewHost } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';

interface ParameterControlBindings {
    host: ParameterViewHost;
    container: Element;
    boundEvents: BoundParameterEvents;
    eventDisposers: Array<() => void>;
    onUpdateArrayItemValue: (parameterKey: string, index: number, value: ParameterValue) => void;
    onUpdateParameter: (parameterKey: string, value: ParameterValue) => void;
    onUpdateJsonParameter: (parameterKey: string, json: string, textareaId: string) => void;
    onSetParameterValidity: (parameterKey: string, valid: boolean) => void;
}

const setParameterInputValidity = (element: HTMLInputElement, valid: boolean): void => {
    setControlValidity(element, valid, '.model-parameter-item');
};

const bindParameterControls = ({ host, container, boundEvents, eventDisposers, onUpdateArrayItemValue, onUpdateParameter, onUpdateJsonParameter, onSetParameterValidity }: ParameterControlBindings): void => {
    const updateControl = (_event: Event, element: HTMLElement): void => {
        if (!(element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement)) {
            throw new TypeError('Parameter control must be an input, textarea, or select');
        }
        const key = getDomData(host, element, 'param');
        if (!key) return;
        if (element.classList.contains('json-input')) {
            if (!(element instanceof HTMLTextAreaElement)) throw new TypeError('JSON parameter control must be a textarea');
            onUpdateJsonParameter(key, element.value, element.id);
            return;
        }
        if (element.classList.contains('array-item-input')) {
            if (!(element instanceof HTMLInputElement)) throw new TypeError('Array item control must be an input');
            const index = Number(getDomData(host, element, 'index'));
            setParameterInputValidity(element, element.validity.valid);
            const inputs = host.dom.resolveAll(`.array-item-input[data-param="${CSS.escape(key)}"]`, container);
            if (element.validity.valid && Number.isInteger(index)) {
                const value = element.type === 'checkbox' ? element.checked : element.type === 'number' && Number.isFinite(element.valueAsNumber) ? element.valueAsNumber : element.value;
                onUpdateArrayItemValue(key, index, value);
            }
            onSetParameterValidity(
                key,
                inputs.every((input) => input instanceof HTMLInputElement && input.validity.valid)
            );
            return;
        }
        if (element instanceof HTMLInputElement && element.type === 'number') {
            setParameterInputValidity(element, element.validity.valid);
            if (element.validity.valid) onUpdateParameter(key, Number.isFinite(element.valueAsNumber) ? element.valueAsNumber : null);
            onSetParameterValidity(key, element.validity.valid);
            return;
        }
        if (element instanceof HTMLInputElement && element.type === 'checkbox') {
            onUpdateParameter(key, element.checked);
            updateToggleLabel(element);
            return;
        }
        onUpdateParameter(key, element.value);
    };
    const selector = 'input[data-param], textarea[data-param], select[data-param], .array-item-input, .json-input';
    registerHandlers(host, container, selector, 'input', boundEvents, eventDisposers, updateControl);
    registerHandlers(host, container, selector, 'change', boundEvents, eventDisposers, updateControl);
};

export { bindParameterControls };
