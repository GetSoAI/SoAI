/* SoAI - Model detail page control layer parameter view manager events [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { setControlValidity } from '@core/dom/formValidity.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ParameterValue } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { getDomData, registerHandlers } from '@pages/modeldetail/controllers/parameterviewmanager/dom.ts';
import type { ParameterViewHost } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';

interface ParameterControlBindings {
    host: ParameterViewHost;
    container: Element;
    boundElements: Set<Element>;
    eventDisposers: Array<() => void>;
    onUpdateArrayItemValue: (parameterKey: string, index: number, value: ParameterValue) => void;
    onUpdateParameter: (parameterKey: string, value: ParameterValue) => void;
    onUpdateJsonParameter: (parameterKey: string, json: string, textareaId: string) => void;
    onSetParameterValidity: (parameterKey: string, valid: boolean) => void;
}

const setParameterInputValidity = (element: HTMLInputElement, valid: boolean): void => {
    setControlValidity(element, valid, '.model-parameter-item');
};

const bindParameterControls = ({ host, container, boundElements, eventDisposers, onUpdateArrayItemValue, onUpdateParameter, onUpdateJsonParameter, onSetParameterValidity }: ParameterControlBindings): void => {
    registerHandlers(host, container, '.array-item-input', 'input', boundElements, eventDisposers, (_event: Event, element: HTMLElement) => {
        if (!(element instanceof HTMLInputElement)) {
            throw new TypeError('Array item input must be an HTMLInputElement');
        }
        const key = getDomData(host, element, 'param');
        const index = Number(getDomData(host, element, 'index'));
        if (key && Number.isInteger(index)) {
            const value = element.type === 'checkbox' ? element.checked : element.type === 'number' && Number.isFinite(element.valueAsNumber) ? element.valueAsNumber : element.value;
            onUpdateArrayItemValue(key, index, value);
        }
    });
    registerHandlers(host, container, 'input[type="number"][data-param]', 'input', boundElements, eventDisposers, (_event: Event, element: HTMLElement) => {
        if (!(element instanceof HTMLInputElement)) {
            throw new TypeError('Numeric parameter control must be an HTMLInputElement');
        }
        const key = getDomData(host, element, 'param');
        if (!key) {
            return;
        }
        if (!element.validity.valid) {
            setParameterInputValidity(element, false);
            onSetParameterValidity(key, false);
            return;
        }
        setParameterInputValidity(element, true);
        onSetParameterValidity(key, true);
        const step = element.step ? Number(element.step) : NaN;
        const numericValue = element.valueAsNumber;
        const parsed = Number.isFinite(numericValue) && (!Number.isNaN(step) && step < 1 ? true : Number.isInteger(numericValue)) ? numericValue : null;
        onUpdateParameter(key, parsed);
    });
    registerHandlers(host, container, 'input[data-param], textarea[data-param], select[data-param]', 'change', boundElements, eventDisposers, (_event: Event, element: HTMLElement) => {
        if (element.matches('.array-item-input, input[type="number"]')) {
            return;
        }
        const key = getDomData(host, element, 'param');
        if (!key) {
            return;
        }
        if (element instanceof HTMLInputElement && element.type === 'checkbox') {
            onUpdateParameter(key, element.checked);
            const label = host.pageDom.optional('.toggle-label', element.closest('.toggle-switch') ?? undefined);
            if (label) {
                host.pageDom.updateText(label, element.checked ? i18n.t('common.boolean.true') : i18n.t('common.boolean.false'));
            }
            return;
        }
        if (element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) {
            onUpdateParameter(key, element.value);
            return;
        }
        throw new TypeError('Parameter control change target must be an HTMLInputElement, HTMLTextAreaElement, or HTMLSelectElement');
    });
    registerHandlers(host, container, '.json-input', 'focusout', boundElements, eventDisposers, (_event: Event, element: HTMLElement) => {
        const key = getDomData(host, element, 'param');
        if (!key) {
            return;
        }
        if (!(element instanceof HTMLTextAreaElement)) {
            throw new TypeError('JSON parameter control must be an HTMLTextAreaElement');
        }
        onUpdateJsonParameter(key, element.value, element.id);
    });
};

export { bindParameterControls };
