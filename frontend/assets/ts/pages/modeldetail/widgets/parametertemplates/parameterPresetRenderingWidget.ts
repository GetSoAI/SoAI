/* SoAI - Parameter preset rendering widget [frontend/assets/ts/pages/modeldetail/widgets/parametertemplates/parameterPresetRenderingWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { ensureArray } from '@core/normalize.ts';
import { isTrustedHtml, renderLabelAttributes, securityApi } from '@core/security/public.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { renderToggleSwitch } from '@core/toggleSwitch.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM, ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM } from '@features/modeldetail/public.ts';
import type { ParameterTemplateContext } from '@pages/modeldetail/contracts/parameterTypes.ts';
import type { ArrayInputProps, ArrayItemProps, BooleanInputProps, ChoiceInputProps, NumericInputProps, ObjectInputProps, TextInputProps } from '@pages/modeldetail/widgets/parametertemplates/types.ts';

const requireTemplateIcon = (context: ParameterTemplateContext, key: string): string => {
    const iconMarkup = context.icons[key];
    if (!isTrustedHtml(iconMarkup) || !iconMarkup.html.trim()) {
        throw new Error(`ModelDetail parameter template requires icon "${key}"`);
    }
    return iconMarkup.html;
};

const renderBooleanInput = (_context: ParameterTemplateContext, { id, key, value }: BooleanInputProps): string =>
    renderToggleSwitch({
        id,
        checked: value === true || value === 'true',
        labels: { trueLabel: i18n.t('common.boolean.true'), falseLabel: i18n.t('common.boolean.false') },
        inputDataset: { 'param': key }
    });

const renderPlaceholderAttribute = (placeholder: string | undefined): string => (placeholder ? ` placeholder="${securityApi.escapeAttribute(placeholder)}"` : '');

const renderNumericInput = (_context: ParameterTemplateContext, props: NumericInputProps): string => {
    const { id, key, value, minimum, maximum, numericType, placeholder } = props;
    const step = numericType === 'integer' ? 1 : 0.01;
    const normalizedValue = value === null || value === undefined ? '' : String(value);
    const minMarkup = minimum !== undefined ? ` min="${securityApi.escapeAttribute(minimum)}"` : '';
    const maxMarkup = maximum !== undefined ? ` max="${securityApi.escapeAttribute(maximum)}"` : '';
    return `<input type="number" id="${securityApi.escapeAttribute(id)}" data-param="${securityApi.escapeAttribute(key)}" value="${securityApi.escapeAttribute(normalizedValue)}" step="${step}" class="model-parameter-input glass-surface-full"${minMarkup}${maxMarkup}${renderPlaceholderAttribute(placeholder)}>`;
};

const renderChoiceInput = (_context: ParameterTemplateContext, props: ChoiceInputProps): string => {
    const { id, key, value, choices } = props;
    const options = isArray(choices) ? choices.map((choice) => `<option value="${securityApi.escapeAttribute(String(choice))}" ${Object.is(choice, value) ? 'selected' : ''}>${securityApi.escapeHtml(String(choice))}</option>`).join('') : '';
    return renderStandardDropdownSelectControl(`<select id="${securityApi.escapeAttribute(id)}" data-param="${securityApi.escapeAttribute(key)}" class="model-parameter-input glass-surface-full">${options}</select>`);
};

const renderTextInput = (_context: ParameterTemplateContext, props: TextInputProps): string => {
    const { id, key, value, placeholder } = props;
    return `<input type="text" id="${securityApi.escapeAttribute(id)}" data-param="${securityApi.escapeAttribute(key)}" value="${securityApi.escapeAttribute(value ?? '')}" class="model-parameter-input glass-surface-full"${renderPlaceholderAttribute(placeholder)}>`;
};

const renderArrayItem = (context: ParameterTemplateContext, props: ArrayItemProps): string => {
    const { key, index, value, itemType, fixedArity } = props;
    const removeIcon = requireTemplateIcon(context, 'CLOSE');
    const removeLabel = i18n.t('modelDetail.parameters.removeItem');
    const safeKey = securityApi.escapeAttribute(key);
    const safeValue = securityApi.escapeAttribute(value);
    const inputType = itemType === 'integer' || itemType === 'float' ? 'number' : itemType === 'boolean' ? 'checkbox' : 'text';
    const checked = inputType === 'checkbox' && value === true ? ' checked' : '';
    const step = itemType === 'integer' ? ' step="1"' : itemType === 'float' ? ' step="any"' : '';
    const removeButton = fixedArity ? '' : `<button type="button" class="btn-remove-item ui-icon-button ui-icon-button--xs ui-variant-danger" data-action="${ACTION_PARAMETER_TEMPLATE_REMOVE_ARRAY_ITEM}" data-param="${safeKey}" data-index="${index}"${renderLabelAttributes(removeLabel).html}>${renderIconSlot(removeIcon).html}</button>`;
    return `
        <div class="array-item" data-index="${index}">
            <input type="${inputType}" class="model-parameter-input glass-surface-full array-item-input" data-param="${safeKey}" data-index="${index}" value="${safeValue}"${step}${checked}>
            ${removeButton}
        </div>`;
};

const renderArrayInput = (context: ParameterTemplateContext, props: ArrayInputProps): string => {
    const { id, key, value, itemType, valueCount } = props;
    const addIcon = requireTemplateIcon(context, 'ADD');
    const fixedArity = valueCount !== undefined;
    const items = fixedArity ? Array.from({ length: valueCount }, (_unused, index) => ensureArray(value)[index] ?? '') : ensureArray(value);
    const itemsMarkup = items.map((item, index) => renderArrayItem(context, { key, index, value: item, itemType, fixedArity })).join('');
    const baseAddLabel = i18n.t('modelDetail.parameters.addItem');
    const typedAddLabel = itemType ? i18n.t('modelDetail.parameters.addItemWithType', { itemType }) : '';
    const addLabel = typedAddLabel || baseAddLabel;
    const safeKey = securityApi.escapeAttribute(key);
    const safeItemType = securityApi.escapeAttribute(itemType ?? '');
    return `
        <div class="array-input-wrapper" data-param="${safeKey}">
            <div class="array-items" id="${securityApi.escapeAttribute(id)}-items">${itemsMarkup}</div>
            ${fixedArity ? '' : `<button type="button" class="ui-icon-button ui-variant-accent add-array-item" data-action="${ACTION_PARAMETER_TEMPLATE_ADD_ARRAY_ITEM}" data-param="${safeKey}" data-item-type="${safeItemType}"${renderLabelAttributes(addLabel).html}>${renderIconSlot(addIcon).html}</button>`}
        </div>`;
};

const renderObjectInput = (_context: ParameterTemplateContext, props: ObjectInputProps): string => {
    const { id, key, value } = props;
    const normalized = value && isObject(value) ? JSON.stringify(value, null, 2) : value || '{}';
    const safeValue = securityApi.escapeHtml(normalized);
    return `
        <div class="json-input-wrapper">
            <textarea dir="ltr" id="${securityApi.escapeAttribute(id)}" data-param="${securityApi.escapeAttribute(key)}" class="model-parameter-textarea glass-surface-full json-input" rows="4" placeholder='{"key": "value"}'>${safeValue}</textarea>
            <div class="json-validation" id="${securityApi.escapeAttribute(id)}-validation"></div>
        </div>`;
};

export { renderArrayInput, renderBooleanInput, renderChoiceInput, renderNumericInput, renderObjectInput, renderTextInput };
