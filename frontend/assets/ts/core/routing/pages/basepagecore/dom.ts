/* SoAI - Shared routing base page core DOM contracts [frontend/assets/ts/core/routing/pages/basepagecore/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { isChangeDispatchTarget } from '@core/routing/pages/basepagecore/guards.ts';
import type { SetUIValueOptions } from '@core/routing/pages/pagetypes/public.ts';
import { isFunction, isNullOrUndefined, isString } from '@core/typeGuards.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';

interface PageUiValueHost {
    getElement(selector: string | Element, context?: Element): Element | null;
    updateAttribute(target: string | Element, attribute: string, value: string | null, context?: Element | Document | null): void;
    updateText(target: string | Element, text: string, context?: Element | Document | null): void;
    setDataAttribute(target: string | Element, name: string, value: string | null, context?: Element | Document | null): void;
    toggleVisibility(selector: string | Element[], visible: boolean): void;
}

const setBasePageUIValue = (host: PageUiValueHost, target: string | Element, value: JsonValue, { data = null, toggle = null, element = null, formatter, attribute, allowNull, skipChangeEvent = false }: SetUIValueOptions = {}): void => {
    const resolvedElement = element || host.getElement(target);
    if (!resolvedElement) {
        return;
    }

    const resolvedValue = isFunction(formatter) ? formatter(value, resolvedElement) : value;

    if (isNullOrUndefined(resolvedValue)) {
        if (allowNull) {
            if (attribute) {
                host.updateAttribute(resolvedElement, attribute, null);
            } else if (resolvedElement instanceof HTMLInputElement || resolvedElement instanceof HTMLTextAreaElement || resolvedElement instanceof HTMLSelectElement) {
                resolvedElement.value = '';
            } else {
                host.updateText(resolvedElement, '');
            }
            if (data) {
                for (const [key, dataValue] of Object.entries(data)) {
                    host.setDataAttribute(resolvedElement, key, dataValue);
                }
            }
            if (toggle !== null && toggle !== undefined) {
                host.toggleVisibility([resolvedElement], Boolean(toggle));
            }
            return;
        }
        throw err(`Value is required for ${resolvedElement.tagName.toLowerCase()}`);
    }

    const applyChecked = (checked: boolean): void => {
        if (!(resolvedElement instanceof HTMLInputElement)) {
            throw err('Checked attribute requires an input element');
        }
        resolvedElement.checked = checked;
        host.updateAttribute(resolvedElement, 'checked', checked ? '' : null);
    };

    const applyValueText = (text: string): void => {
        if (resolvedElement instanceof HTMLInputElement) {
            if (resolvedElement.type === 'checkbox') {
                throw err('Checkbox input requires checked attribute');
            }
            resolvedElement.value = text;
            host.updateAttribute(resolvedElement, 'value', text);
            return;
        }
        if (resolvedElement instanceof HTMLTextAreaElement) {
            resolvedElement.value = text;
            host.updateAttribute(resolvedElement, 'value', text);
            return;
        }
        if (resolvedElement instanceof HTMLSelectElement) {
            setSelectValueAndSyncDefault(resolvedElement, text);
            return;
        }
        host.updateText(resolvedElement, text);
    };

    if (attribute) {
        if (attribute === 'checked') {
            if (typeof resolvedValue !== 'boolean') {
                throw err('Checked attribute requires boolean value');
            }
            applyChecked(resolvedValue);
        } else if (attribute === 'value') {
            if (!isString(resolvedValue) && typeof resolvedValue !== 'number') {
                throw err('Value attribute requires string or number');
            }
            applyValueText(String(resolvedValue));
        } else {
            if (!isString(resolvedValue) && typeof resolvedValue !== 'number') {
                throw err('Attribute value requires string or number');
            }
            host.updateAttribute(resolvedElement, attribute, String(resolvedValue));
        }
    } else if (resolvedElement instanceof HTMLInputElement && resolvedElement.type === 'checkbox') {
        if (typeof resolvedValue !== 'boolean') {
            throw err('Checkbox input requires boolean value');
        }
        applyChecked(resolvedValue);
    } else if (isString(resolvedValue) || typeof resolvedValue === 'number') {
        applyValueText(String(resolvedValue));
    } else if (typeof resolvedValue === 'boolean') {
        applyValueText(String(resolvedValue));
    } else {
        throw err(`Unsupported value type for ${resolvedElement.tagName.toLowerCase()}`);
    }

    if (data) {
        for (const [key, dataValue] of Object.entries(data)) {
            host.setDataAttribute(resolvedElement, key, dataValue);
        }
    }
    if (toggle !== null && toggle !== undefined) {
        host.toggleVisibility([resolvedElement], Boolean(toggle));
    }
    if (!skipChangeEvent && isChangeDispatchTarget(resolvedElement)) {
        resolvedElement.dispatchEvent(new Event('change'));
    }
};

export { setBasePageUIValue };
export type { PageUiValueHost };
