/* SoAI - Shared UI select control [frontend/assets/ts/core/ui/dropdown/selectControl.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiAttributes, uiText, type UiAttributeValue } from '@core/security/uiHtml.ts';

interface DropdownSelectControlOptions {
    selectMarkup: string;
    shellClassName?: string;
}

interface RepeatableDropdownSelectOption {
    value: string;
    label: string;
}

interface RepeatableDropdownSelectControlOptions {
    id: string;
    className: string;
    shellClassName?: string;
    selectionLabel: string;
    accessibleLabel: string;
    options: readonly RepeatableDropdownSelectOption[];
    attributes?: Readonly<Record<string, UiAttributeValue>>;
}

const REPEATABLE_SELECT_SENTINEL = '';

const renderDropdownSelectControl = ({ selectMarkup, shellClassName }: DropdownSelectControlOptions): string => {
    const shellClass = shellClassName ? `dropdown-select ${shellClassName}` : 'dropdown-select';
    return `<span class="${shellClass}">${selectMarkup}</span>`;
};

const renderStandardDropdownSelectControl = (selectMarkup: string): string => {
    return renderDropdownSelectControl({ selectMarkup });
};

const renderRepeatableDropdownSelectControl = (inputArguments: RepeatableDropdownSelectControlOptions): TrustedHtml => {
    const values = new Set<string>();
    const labels = new Set<string>();
    const optionMarkup = inputArguments.options
        .map((option) => {
            const value = option.value.trim();
            const label = option.label.trim();
            if (!value || !label) throw new Error('Repeatable dropdown options require non-empty values and labels');
            if (values.has(value)) throw new Error(`Repeatable dropdown includes duplicate value: ${value}`);
            if (labels.has(label)) throw new Error(`Repeatable dropdown includes duplicate label: ${label}`);
            values.add(value);
            labels.add(label);
            return `<option value="${uiAttr(value).html}">${uiText(label).html}</option>`;
        })
        .join('');
    const shellClassName = `dropdown-select dropdown-select--selection-prefix${inputArguments.shellClassName ? ` ${inputArguments.shellClassName}` : ''}`;
    const attributes = uiAttributes({ ...inputArguments.attributes, 'aria-label': inputArguments.accessibleLabel, 'data-repeatable-dropdown-select': 'true' });
    return toTrustedUiHtml(`<span class="${uiAttr(shellClassName).html}"><span class="dropdown-select__selection-label" aria-hidden="true">${uiText(inputArguments.selectionLabel).html}</span><select id="${uiAttr(inputArguments.id).html}" class="${uiAttr(inputArguments.className).html}"${attributes.html}><option value="${REPEATABLE_SELECT_SENTINEL}" selected disabled hidden></option>${optionMarkup}</select></span>`);
};

const consumeRepeatableDropdownSelection = (select: HTMLSelectElement): string => {
    if (select.dataset['repeatableDropdownSelect'] !== 'true') throw new Error('Repeatable dropdown selection requires a repeatable select');
    const value = select.value.trim();
    setSelectValueAndSyncDefault(select, REPEATABLE_SELECT_SENTINEL);
    if (!value) throw new Error('Repeatable dropdown selection is empty');
    return value;
};

const syncRepeatableDropdownSelect = (select: HTMLSelectElement, selectionLabel: string, accessibleLabel: string): void => {
    if (select.dataset['repeatableDropdownSelect'] !== 'true') throw new Error('Repeatable dropdown synchronization requires a repeatable select');
    const label = dom.resolve('.dropdown-select__selection-label', select.parentElement);
    if (!(label instanceof HTMLElement)) throw new Error('Repeatable dropdown selection label is missing');
    label.textContent = selectionLabel;
    select.setAttribute('aria-label', accessibleLabel);
    setSelectValueAndSyncDefault(select, REPEATABLE_SELECT_SENTINEL);
};

export { consumeRepeatableDropdownSelection, renderDropdownSelectControl, renderRepeatableDropdownSelectControl, renderStandardDropdownSelectControl, syncRepeatableDropdownSelect };
export type { RepeatableDropdownSelectControlOptions, RepeatableDropdownSelectOption };
