/* SoAI - Shared settings markup helpers [frontend/assets/ts/core/settings/settingsMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { securityApi } from '@core/security/public.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { renderDropdownSelectControl, renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import type { SectionOptions, SelectControlOptions, SettingItemOptions, SettingsGroupOptions, SettingsRecordListOptions, SettingsStatusBadgeTone, SettingsSubgroupOptions, SliderControlOptions, ToggleControlOptions } from '@core/settings/contracts.ts';

const isValidAttributeName = (name: string): boolean => /^[a-zA-Z][a-zA-Z0-9_:-]*$/.test(name);

const renderAttributesMarkup = (attributes?: Record<string, string | boolean | null | undefined>): string => {
    if (!attributes) {
        return '';
    }

    let markup = '';
    for (const [name, value] of Object.entries(attributes)) {
        if (!isValidAttributeName(name)) {
            throw new Error(`Invalid attribute name: ${name}`);
        }
        if (value === null || value === undefined || value === false) {
            continue;
        }
        if (value === true) {
            markup += ` ${name}`;
            continue;
        }
        markup += ` ${name}="${securityApi.escapeAttribute(value)}"`;
    }
    return markup;
};

const renderSection = (options: SectionOptions): string => {
    const classSuffix = options.className ? ` ${securityApi.escapeAttribute(options.className)}` : '';
    return `<div class="settings-section${classSuffix}">${renderSectionHeader(options)}<div class="section-content">${options.content}</div></div>`;
};

const renderSectionHeader = (options: SectionOptions): string => {
    const description = options.description ? `<p class="section-description">${options.description}</p>` : '';
    const header = `<h2 class="section-title">${options.title}</h2>`;
    return `<div class="section-header"><div>${header}${description}</div>${renderSectionHeaderActions(options.trailing)}</div>`;
};

const renderSectionHeaderActions = (trailing?: string): string => {
    return trailing ? `<div class="section-header-end">${trailing}</div>` : '';
};

const renderSettingItem = ({ label, help, control, className, fieldKey, dataset: dataAttributesMap, attributes }: SettingItemOptions): string => {
    const resolvedClassName = className ? `setting-change-surface ${securityApi.escapeAttribute(className)}` : 'setting-change-surface';
    const attributesMarkup = renderAttributesMarkup(attributes);

    let dataAttributes = fieldKey ? ` data-field-key="${securityApi.escapeAttribute(fieldKey)}"` : '';
    if (dataAttributesMap) {
        for (const key of Object.keys(dataAttributesMap)) {
            if (key === 'fieldKey') {
                throw new Error('renderSettingItem fieldKey must use the dedicated fieldKey option');
            }
            if (!isValidAttributeName(`data-${key}`)) {
                throw new Error(`Invalid setting item data attribute name: ${key}`);
            }
            const value = dataAttributesMap[key];
            if (value !== null && value !== undefined) {
                dataAttributes += ` data-${key}="${securityApi.escapeAttribute(value)}"`;
            }
        }
    }
    return `<div class="setting-item ${resolvedClassName}"${dataAttributes}${attributesMarkup}><div class="setting-info"><label class="setting-label">${label}</label>${help ? `<span class="setting-help">${help}</span>` : ''}</div><div class="setting-control">${control}</div></div>`;
};

const renderSettingsGroup = (items: string[], options: SettingsGroupOptions = {}): string => {
    const classSuffix = options.className ? ` ${securityApi.escapeAttribute(options.className)}` : '';
    const attributesMarkup = renderAttributesMarkup(options.attributes);
    return `<div class="settings-group${classSuffix}"${attributesMarkup}>${items.join('')}</div>`;
};

const renderSettingsSubgroup = (options: SettingsSubgroupOptions): string => {
    const classSuffix = options.className ? ` ${securityApi.escapeAttribute(options.className)}` : '';
    const attributesMarkup = renderAttributesMarkup(options.attributes);
    const description = options.description ? `<p class="subgroup-description">${options.description}</p>` : '';
    const trailing = options.trailing ? `<div class="subgroup-header-actions">${options.trailing}</div>` : '';
    const tagName = options.tagName ?? 'div';
    return `<${tagName} class="settings-subgroup${classSuffix}"${attributesMarkup}><div class="subgroup-header"><div><h3 class="subgroup-title">${options.title}</h3>${description}</div>${trailing}</div>${options.content}</${tagName}>`;
};

const renderSettingsRecordList = (options: SettingsRecordListOptions): string => {
    const classSuffix = options.className ? ` ${securityApi.escapeAttribute(options.className)}` : '';
    const idMarkup = options.id ? ` id="${securityApi.escapeAttribute(options.id)}"` : '';
    const attributesMarkup = renderAttributesMarkup(options.attributes);
    const content = options.items.length ? options.items.join('') : options.empty;
    return `<div${idMarkup} class="settings-record-list${classSuffix}"${attributesMarkup}>${content}</div>`;
};

const renderSettingsStatusBadge = (label: string, tone: SettingsStatusBadgeTone): string => {
    return `<span class="settings-record-badge settings-record-badge--${tone}">${securityApi.escapeHtml(label)}</span>`;
};

const renderSettingsTextValue = (value: string, id?: string): string => {
    const idMarkup = id ? ` id="${securityApi.escapeAttribute(id)}"` : '';
    return `<span${idMarkup} class="settings-control-value">${securityApi.escapeHtml(value)}</span>`;
};

const renderSettingsCodeValue = (value: string, id?: string, className?: string): string => {
    const idMarkup = id ? ` id="${securityApi.escapeAttribute(id)}"` : '';
    const classMarkup = className ? ` ${securityApi.escapeAttribute(className)}` : '';
    return `<code${idMarkup} class="settings-control-code${classMarkup}">${securityApi.escapeHtml(value)}</code>`;
};

const renderToggleControl = (options: ToggleControlOptions): string => {
    return renderToggleSwitch({
        id: options.id,
        checked: options.checked,
        labels: options.labels,
        inline: options.inline === true,
        disabled: options.disabled === true,
        inputClassName: options.inputClassName,
        wrapperClassName: options.wrapperClassName,
        inputDataset: options.inputDataset,
        wrapperDataset: options.wrapperDataset,
        showLabel: options.showLabel === true
    });
};

const renderSelectControl = ({ id, options, selected, disabled, wide, compact }: SelectControlOptions): string => {
    const selectedValue = selected === null || selected === undefined ? '' : selected;
    const classes = wide ? 'setting-input setting-input--wide' : 'setting-input';
    const classMarkup = compact === true ? '' : ` class="${classes}"`;
    const selectMarkup = `<select id="${securityApi.escapeAttribute(id)}"${classMarkup}${renderControlDisabledAttributes(disabled === true)}>${options
        .map((option) => {
            const value = option.value === null || option.value === undefined ? '' : option.value;
            const isSelected = value === selectedValue;
            return `<option value="${securityApi.escapeAttribute(value)}"${isSelected ? ' selected' : ''}${option.disabled ? ' disabled' : ''}>${securityApi.escapeHtml(option.label)}</option>`;
        })
        .join('')}</select>`;
    return compact === true ? renderDropdownSelectControl({ shellClassName: 'dropdown-select--sm', selectMarkup }) : renderStandardDropdownSelectControl(selectMarkup);
};

const renderSliderControl = ({ id, valueId, min, max, step, value, valueLabel }: SliderControlOptions): string => {
    return `<div class="settings-slider-control"><input type="range" id="${securityApi.escapeAttribute(id)}" class="settings-slider" min="${securityApi.escapeAttribute(String(min))}" max="${securityApi.escapeAttribute(String(max))}" value="${securityApi.escapeAttribute(String(value))}" step="${securityApi.escapeAttribute(String(step))}"><span id="${securityApi.escapeAttribute(valueId)}" class="settings-slider-value">${securityApi.escapeHtml(valueLabel)}</span></div>`;
};

export { renderSection, renderSelectControl, renderSettingItem, renderSettingsCodeValue, renderSettingsGroup, renderSettingsRecordList, renderSettingsStatusBadge, renderSettingsSubgroup, renderSettingsTextValue, renderSliderControl, renderToggleControl };
