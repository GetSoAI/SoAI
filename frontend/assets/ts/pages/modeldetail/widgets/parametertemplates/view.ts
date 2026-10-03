/* SoAI - Model detail page widgets parameter templates rendering [frontend/assets/ts/pages/modeldetail/widgets/parametertemplates/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, securityApi } from '@core/security/public.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderSettingItem } from '@core/settings/settingsMarkup.ts';
import { isArray } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject } from '@core/types/jsonValues.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { ACTION_BACKEND_DOCUMENTATION, ACTION_PARAMETER_NAVIGATE_CATEGORY, ACTION_PARAMETER_REVERT, ACTION_PARAMETER_SELECT_GROUP, ACTION_PARAMETER_SELECT_VIEW } from '@features/modeldetail/public.ts';
import { resolveParameterCategoryLabel } from '@pages/modeldetail/contracts/parameterCategoryMetadata.ts';
import type { NamedParameter, ParameterCollection, ParameterDefinition, ParameterTemplateContext, ParameterGroup, ParameterTemplateOptions, ParameterView } from '@pages/modeldetail/contracts/parameterTypes.ts';
import { PARAMETER_GROUPS, PARAMETER_VIEWS } from '@pages/modeldetail/controllers/parameterviewmanager/constants.ts';
import { requireConfiguredIcon } from '@pages/modeldetail/guards/guards.ts';
import { renderArrayInput, renderBooleanInput, renderChoiceInput, renderNumericInput, renderObjectInput, renderTextInput } from '@pages/modeldetail/widgets/parametertemplates/parameterPresetRenderingWidget.ts';
import { createRenderContext, normalizeParameterType, resolveParameterDefinition, resolveParameterInputId, resolveParameterValue } from '@pages/modeldetail/widgets/parametertemplates/state.ts';

type ParameterCategoryGroup = { key: string; label: string; parameters: NamedParameter[] };

const WIDE_PARAMETER_TYPES = new Set(['array', 'object']);

const renderParameterControlInternal = (context: ParameterTemplateContext, parameter: NamedParameter): string => {
    const { key } = parameter;
    const definition = resolveParameterDefinition(parameter.definition);
    const { type = 'string', minimum, maximum, itemType, valueCount, choices } = definition;
    const resolvedValue = resolveParameterValue(parameter, definition);
    const id = resolveParameterInputId(key);
    const parameterType = normalizeParameterType(type);
    const placeholder = resolvedValue === null ? i18n.t('modelDetail.parameters.backendDefault') : undefined;

    if (parameterType === 'boolean') {
        return renderBooleanInput(context, {
            id,
            key,
            value: typeof resolvedValue === 'boolean' || typeof resolvedValue === 'string' ? resolvedValue : null
        });
    }

    if (parameterType === 'integer' || parameterType === 'float') {
        return renderNumericInput(context, {
            id,
            key,
            value: typeof resolvedValue === 'number' || typeof resolvedValue === 'string' ? resolvedValue : null,
            minimum,
            maximum,
            numericType: parameterType,
            placeholder
        });
    }

    if (parameterType === 'array') {
        return renderArrayInput(context, {
            id,
            key,
            value: isJsonArray(resolvedValue) ? resolvedValue : [],
            itemType,
            valueCount
        });
    }

    if (parameterType === 'object') {
        const objectValue = isJsonObject(resolvedValue) ? resolvedValue : typeof resolvedValue === 'string' ? resolvedValue : null;
        return renderObjectInput(context, {
            id,
            key,
            value: objectValue
        });
    }

    if (isArray(choices) && choices.length > 0) {
        return renderChoiceInput(context, {
            id,
            key,
            value: resolvedValue ?? undefined,
            choices
        });
    }

    return renderTextInput(context, { id, key, value: typeof resolvedValue === 'string' ? resolvedValue : '', placeholder });
};

const renderBadge = (className: string, label: string, hidden = false): string => `<span class="${securityApi.escapeAttribute(`param-badge ${className}${hidden ? ' u-hidden' : ''}`)}">${securityApi.escapeHtml(label)}</span>`;

const renderParameterBadges = (context: ParameterTemplateContext, parameter: NamedParameter, definition: ParameterDefinition): string => {
    const group = definition.group ?? 'unknown';
    const requiresReload = definition.requiresReload === true;
    const groupImpliedByReload = requiresReload && group === 'startup';
    return [renderBadge('custom', i18n.t('modelDetail.parameters.badges.custom'), !context.isCustomized(parameter)), requiresReload ? renderBadge('reload', i18n.t('modelDetail.parameters.badges.requiresReload')) : '', groupImpliedByReload ? '' : renderBadge(`group ${group}`, context.formatGroupLabel(group))].join('');
};

const renderParameterHelp = (context: ParameterTemplateContext, definition: ParameterDefinition): string => {
    const { description = '', aliases = [], type, itemType, minimum, maximum } = definition;
    const hints = [aliases.length > 0 ? `${i18n.t('modelDetail.parameters.aliasesPrefix')} ${aliases.join(', ')}` : '', type === 'array' && itemType ? context.describeArray(itemType) : '', type === 'object' ? i18n.t('modelDetail.parameters.jsonObject') : '', minimum !== undefined && maximum !== undefined ? i18n.t('modelDetail.parameters.range', { min: minimum, max: maximum }) : ''].filter(Boolean);
    const descriptionMarkup = description ? `<span class="model-parameter-description">${securityApi.escapeHtml(description)}</span>` : '';
    const hintsMarkup = hints.length ? `<span class="model-parameter-hints">${hints.map((hint) => `<span>${securityApi.escapeHtml(hint)}</span>`).join('')}</span>` : '';
    return descriptionMarkup + hintsMarkup;
};

const renderRevertButton = (context: ParameterTemplateContext, key: string): string => {
    const label = i18n.t('modelDetail.parameters.revertChange');
    const icon = requireConfiguredIcon(context.icons, 'REVERT', { subject: 'ModelDetail parameter templates', verb: 'require' });
    return `<button type="button" class="ui-icon-button ui-icon-button--xs model-parameter-revert u-hidden" data-action="${ACTION_PARAMETER_REVERT}" data-param="${securityApi.escapeAttribute(key)}" ${renderLabelAttributes(label).html}>${renderIconSlot(icon).html}</button>`;
};

const renderParameter = (context: ParameterTemplateContext, parameter: NamedParameter): string => {
    const { key } = parameter;
    const definition = resolveParameterDefinition(parameter.definition);
    const { displayName, category = 'other', group = 'unknown', type } = definition;
    const label = typeof displayName === 'string' && displayName.trim().length > 0 ? displayName.trim() : key;
    const isWide = WIDE_PARAMETER_TYPES.has(normalizeParameterType(type));
    return renderSettingItem({
        label: `<span class="model-parameter-name">${securityApi.escapeHtml(label)}</span><span class="model-parameter-badges">${renderParameterBadges(context, parameter, definition)}</span>`,
        help: renderParameterHelp(context, definition),
        control: `${renderRevertButton(context, key)}${renderParameterControlInternal(context, parameter)}`,
        className: `model-parameter-item${isWide ? ' full-width' : ''}`,
        dataset: { 'param': key, category, group }
    });
};

const groupParametersByCategory = (parameters: ParameterCollection, context: ParameterTemplateContext): ParameterCategoryGroup[] => {
    const grouped = new Map<string, NamedParameter[]>();
    for (const [parameterKey, parameterData] of Object.entries(parameters)) {
        const category = parameterData.definition?.category || 'other';
        const entries = grouped.get(category) ?? [];
        entries.push({ key: parameterKey, ...parameterData });
        grouped.set(category, entries);
    }
    return Array.from(grouped, ([key, entries]) => ({ key, label: resolveParameterCategoryLabel(context.categories?.[key], key), parameters: entries }));
};

const renderCount = (className: string, count: number): string => `<span class="${securityApi.escapeAttribute(className)}">${securityApi.escapeHtml(i18n.formatNumber(count))}</span>`;

const renderCategorySection = (context: ParameterTemplateContext, group: ParameterCategoryGroup): string => {
    const count = group.parameters.length;
    return `
        <section class="model-parameter-section parameter-category glass-surface-full" data-category="${uiAttr(group.key).html}" aria-label="${securityApi.escapeAttribute(group.label)}">
            <div class="card-title-bar modeldetail-category-header">
                <h3 class="card-title category-title">${securityApi.escapeHtml(group.label)}</h3>
                <span class="param-count">${securityApi.escapeHtml(i18n.plural('modelDetail.parameters.count', count, { count: i18n.formatNumber(count) }))}</span>
            </div>
            <div class="model-parameter-group setting-grid">${group.parameters.map((parameter) => renderParameter(context, parameter)).join('')}</div>
        </section>`;
};

const renderViewLabel = (view: ParameterView): string => {
    switch (view) {
        case 'all':
            return i18n.t('modelDetail.filters.allParameters');
        case 'customized':
            return i18n.t('modelDetail.parameters.views.customized');
        case 'unsaved':
            return i18n.t('modelDetail.parameters.views.unsaved');
    }
};

const renderGroupLabel = (group: ParameterGroup): string => (group === 'startup' ? i18n.t('modelDetail.filters.groupStartup') : i18n.t('modelDetail.filters.groupInference'));

const renderRailItem = (attributes: string, label: string, count: number, active: boolean): string => `<button type="button" class="ui-button ui-button--sm ui-button-block ui-button-quiet ui-variant-ghost model-parameter-rail-item${active ? ' is-active' : ''}" ${attributes} ${renderLabelAttributes(label).html}><span class="model-parameter-rail-label">${securityApi.escapeHtml(label)}</span>${renderCount('model-parameter-rail-count', count)}</button>`;

const renderParameterRail = (groups: ParameterCategoryGroup[], totalCount: number): string => {
    const views = PARAMETER_VIEWS.map((view) => renderRailItem(`data-action="${ACTION_PARAMETER_SELECT_VIEW}" data-parameter-view="${view}" aria-pressed="${view === 'all'}"`, renderViewLabel(view), view === 'all' ? totalCount : 0, view === 'all')).join('');
    const categories = groups.map((group) => renderRailItem(`data-action="${ACTION_PARAMETER_NAVIGATE_CATEGORY}" data-category="${uiAttr(group.key).html}"`, group.label, group.parameters.length, false)).join('');
    const groupItems = PARAMETER_GROUPS.map((group) => renderRailItem(`data-action="${ACTION_PARAMETER_SELECT_GROUP}" data-parameter-group="${group}" aria-pressed="false"`, renderGroupLabel(group), 0, false)).join('');
    return `<nav class="model-parameter-rail glass-surface-full" data-presence-suspended aria-label="${securityApi.escapeAttribute(i18n.t('modelDetail.parameters.railLabel'))}">
        <div class="model-parameter-rail-views">${views}</div>
        <div class="model-parameter-rail-groups">${groupItems}</div>
        <div class="model-parameter-rail-categories">${categories}</div>
    </nav>`;
};

const renderBackendDocumentationCallout = (context: ParameterTemplateContext): string => {
    const label = i18n.t('modelDetail.buttons.backend_documentation');
    const iconMarkup = requireConfiguredIcon(context.icons, 'BACKEND_DOCUMENTATION', { subject: 'ModelDetail parameter templates', verb: 'require' });
    return `
        <div class="model-parameter-doc-callout glass-surface-full">
            <p class="model-parameter-doc-description">${i18n.t('modelDetail.parameters.backendDocumentationDescription')}</p>
            <a class="ui-button ui-button--sm" id="backend-doc-button" data-action="${ACTION_BACKEND_DOCUMENTATION}" target="_blank" rel="noopener noreferrer" aria-disabled="true" tabindex="-1">${iconMarkup.html}<span>${label}</span></a>
        </div>`;
};

const renderParametersView = (parameters: ParameterCollection, options: ParameterTemplateOptions, emptyStateMarkup: string): string => {
    const context = createRenderContext(options);
    const groups = groupParametersByCategory(parameters, context);
    const sections = groups.map((group) => renderCategorySection(context, group)).join('');
    return `<div class="model-parameter-layout">
        ${renderParameterRail(groups, Object.keys(parameters).length)}
        <div class="model-parameter-sections">
            ${renderBackendDocumentationCallout(context)}
            <div id="modeldetail-parameters-empty" class="u-hidden modeldetail-parameters-empty">${emptyStateMarkup}</div>
            ${sections}
        </div>
    </div>`;
};

const renderParameterControl = (parameter: NamedParameter, options: ParameterTemplateOptions): string => {
    return renderParameterControlInternal(createRenderContext(options), parameter);
};

const renderBackendDocumentation = (options: ParameterTemplateOptions): string => renderBackendDocumentationCallout(createRenderContext(options));

export { renderBackendDocumentation, renderParameterControl, renderParametersView };
