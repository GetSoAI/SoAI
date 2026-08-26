/* SoAI - Shared frontend toggle switch [frontend/assets/ts/core/toggleSwitch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

type ToggleLabelState = {
    trueLabel: string;
    falseLabel: string;
};

type ToggleSwitchOptions = {
    id: string;
    checked: boolean;
    labels: ToggleLabelState;
    inputClassName?: string | undefined;
    wrapperClassName?: string | undefined;
    inline?: boolean | undefined;
    disabled?: boolean | undefined;
    pending?: boolean | undefined;
    inputDataset?: Record<string, string> | undefined;
    wrapperDataset?: Record<string, string> | undefined;
    wrapperTag?: 'label' | 'div' | undefined;
    showLabel?: boolean | undefined;
    ariaLabel?: string | undefined;
    title?: string | undefined;
};

type ActionToggleLabelMode = 'visible' | 'hidden' | 'omitted';

type ActionToggleSwitchOptions = {
    action: string;
    checked: boolean;
    label: string;
    wrapperClassName?: string | undefined;
    inputClassName?: string | undefined;
    labelClassName?: string | undefined;
    wrapperDataset?: Record<string, string> | undefined;
    inputDataset?: Record<string, string> | undefined;
    wrapperTag?: 'label' | 'div' | undefined;
    labelMode?: ActionToggleLabelMode | undefined;
    pending?: boolean | undefined;
    locked?: boolean | undefined;
    disabled?: boolean | undefined;
    ariaLabel?: string | undefined;
    title?: string | undefined;
};

const normalizeLabelState = (labels: ToggleLabelState): ToggleLabelState => {
    if (!labels || !isString(labels.trueLabel) || !isString(labels.falseLabel)) {
        throw new Error('ToggleSwitch requires true/false labels');
    }
    return {
        trueLabel: labels.trueLabel,
        falseLabel: labels.falseLabel
    };
};

const buildDataset = (labels: ToggleLabelState, existing?: Record<string, string>): Record<string, string> => {
    const dataset = isObject(existing) ? { ...existing } : {};
    dataset['toggleLabelTrue'] = labels.trueLabel;
    dataset['toggleLabelFalse'] = labels.falseLabel;
    return dataset;
};

const appendClassName = (tokens: string[], value: string | undefined): void => {
    if (!isString(value) || !value.trim()) {
        return;
    }
    for (const token of value.split(/\s+/)) {
        const normalized = token.trim();
        if (normalized) {
            tokens.push(normalized);
        }
    }
};

const buildClassName = (tokens: readonly string[]): string => tokens.join(' ');

const createToggleSwitch = (options: ToggleSwitchOptions): HTMLElement => {
    if (!options || !isString(options.id) || !options.id.trim()) {
        throw new Error('ToggleSwitch requires a valid id');
    }
    const labels = normalizeLabelState(options.labels);
    const wrapperTag = options.wrapperTag ?? 'label';
    const wrapperClasses = ['toggle-switch'];
    if (options.inline) wrapperClasses.push('toggle-switch--inline');
    if (options.wrapperClassName) wrapperClasses.push(options.wrapperClassName);
    const wrapper = dom.create(wrapperTag, {
        className: wrapperClasses.join(' '),
        dataset: buildDataset(labels, options.wrapperDataset)
    });
    if (options.pending) {
        wrapper.setAttribute('data-pending', 'true');
        wrapper.setAttribute('aria-busy', 'true');
    }
    const inputElement = dom.create('input', {
        type: 'checkbox',
        id: options.id,
        className: options.inputClassName ?? '',
        checked: Boolean(options.checked),
        dataset: buildDataset(labels, options.inputDataset)
    });
    if (!(inputElement instanceof HTMLInputElement)) {
        throw new Error('ToggleSwitch must create an HTMLInputElement');
    }
    if (options.checked) {
        inputElement.setAttribute('checked', '');
    }
    if (options.ariaLabel) {
        inputElement.setAttribute('aria-label', options.ariaLabel);
    }
    if (options.title) {
        setTooltipText(wrapper, options.title);
    }
    setControlDisabledState(inputElement, Boolean(options.disabled));
    const input = inputElement;
    const sliderTag = wrapperTag === 'label' ? 'span' : 'label';
    const slider = dom.create(sliderTag, {
        className: 'slider',
        for: sliderTag === 'label' ? options.id : undefined
    });
    const label = dom.create('span', {
        className: options.showLabel === false ? 'toggle-label visually-hidden' : 'toggle-label',
        textContent: options.checked ? labels.trueLabel : labels.falseLabel
    });
    dom.appendChild(wrapper, [input, slider, label]);
    return wrapper;
};

const renderToggleSwitch = (options: ToggleSwitchOptions): string => serializeElementToHtml(createToggleSwitch(options));

const createActionToggleSwitch = (options: ActionToggleSwitchOptions): HTMLElement => {
    if (!options || !isString(options.action) || !options.action.trim()) {
        throw new Error('ActionToggleSwitch requires a valid action');
    }
    if (!isString(options.label)) {
        throw new Error('ActionToggleSwitch requires a label');
    }
    const pending = options.pending === true;
    const locked = options.locked === true;
    const disabled = options.disabled === true || locked || pending;
    const wrapperClasses = ['toggle-switch', 'toggle-switch--action'];
    if (options.checked) {
        wrapperClasses.push('toggle-switch--checked');
    }
    appendClassName(wrapperClasses, options.wrapperClassName);

    const wrapperOptions: { className: string; dataset?: Record<string, string> } = {
        className: buildClassName(wrapperClasses)
    };
    if (isObject(options.wrapperDataset)) {
        wrapperOptions.dataset = options.wrapperDataset;
    }
    const wrapper = dom.create(options.wrapperTag ?? 'div', wrapperOptions);
    wrapper.setAttribute('data-action', options.action.trim());
    wrapper.setAttribute('role', 'switch');
    wrapper.setAttribute('tabindex', '0');
    wrapper.setAttribute('aria-checked', options.checked ? 'true' : 'false');
    wrapper.setAttribute('aria-disabled', disabled ? 'true' : 'false');
    if (pending) {
        wrapper.setAttribute('data-pending', 'true');
        wrapper.setAttribute('data-toggle-pending', 'true');
        wrapper.setAttribute('aria-busy', 'true');
    }
    if (locked) {
        wrapper.setAttribute('data-toggle-locked', 'true');
    }
    if (options.title) {
        setTooltipText(wrapper, options.title);
    }

    const inputOptions: { type: string; className: string; checked: boolean; dataset?: Record<string, string> } = {
        type: 'checkbox',
        className: options.inputClassName ?? '',
        checked: Boolean(options.checked)
    };
    if (isObject(options.inputDataset)) {
        inputOptions.dataset = options.inputDataset;
    }
    const inputElement = dom.create('input', inputOptions);
    if (!(inputElement instanceof HTMLInputElement)) {
        throw new Error('ActionToggleSwitch must create an HTMLInputElement');
    }
    if (options.checked) {
        inputElement.setAttribute('checked', '');
    }
    inputElement.readOnly = true;
    inputElement.setAttribute('readonly', '');
    inputElement.setAttribute('tabindex', '-1');
    inputElement.setAttribute('aria-hidden', 'true');
    inputElement.setAttribute('aria-label', options.ariaLabel ?? options.label);

    const slider = dom.create('span', {
        className: 'slider'
    });

    if (options.labelMode === 'omitted') {
        dom.appendChild(wrapper, [inputElement, slider]);
        return wrapper;
    }

    const labelClasses: string[] = [];
    appendClassName(labelClasses, options.labelClassName ?? 'toggle-label');
    if (options.labelMode === 'hidden') {
        labelClasses.push('visually-hidden');
    }
    const label = dom.create('span', {
        className: buildClassName(labelClasses),
        textContent: options.label
    });
    dom.appendChild(wrapper, [inputElement, slider, label]);
    return wrapper;
};

const renderActionToggleSwitch = (options: ActionToggleSwitchOptions): string => serializeElementToHtml(createActionToggleSwitch(options));

const isActionToggleInteractionDisabled = (element: Element): boolean => {
    if (!(element instanceof HTMLElement)) {
        return false;
    }
    return element.dataset['togglePending'] === 'true' || element.dataset['pending'] === 'true' || element.getAttribute('aria-disabled') === 'true';
};

const updateToggleLabel = (input: HTMLInputElement, options?: { checked?: boolean | undefined }): void => {
    if (!input || input.type !== 'checkbox') return;
    const toggle = input.closest('.toggle-switch');
    if (!toggle) return;
    const label = dom.resolve('.toggle-label', toggle);
    if (!label) return;
    const trueLabel = dom.getData(input, 'toggleLabelTrue') ?? dom.getData(toggle, 'toggleLabelTrue');
    const falseLabel = dom.getData(input, 'toggleLabelFalse') ?? dom.getData(toggle, 'toggleLabelFalse');
    if (!isString(trueLabel) || !isString(falseLabel)) return;
    const checked = options?.checked ?? input.checked;
    dom.setText(label, checked ? trueLabel : falseLabel);
};

export { createActionToggleSwitch, createToggleSwitch, isActionToggleInteractionDisabled, renderActionToggleSwitch, renderToggleSwitch, updateToggleLabel };
export type { ActionToggleLabelMode, ActionToggleSwitchOptions, ToggleLabelState, ToggleSwitchOptions };
