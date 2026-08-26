/* SoAI - Shared routing base page layout rendering [frontend/assets/ts/core/routing/pages/basepagelayout/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { getRouteRegistry } from '@core/routeregistry/service.ts';
import { i18n } from '@core/i18n/index.ts';
import type { FilterDefinition, GenerateStandardHeaderOptions, HeaderActionDefinition, HeaderStatActionDefinition, HeaderStatDefinition } from '@core/routing/pages/pagetypes/public.ts';
import { buildPageHeaderTitleMarkup } from '@core/routing/pages/basepagelayout/pageHeaderTitle.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { EMPTY_UI_HTML, staticUiHtml, uiAttr, uiAttributes, uiHtml, uiText, type UiAttributeValue } from '@core/security/uiHtml.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isTrustedHtml } from '@core/security/htmlSanitizer.ts';

interface HeaderTemplateHost {
    pageId: string;
    isDetached(): boolean;
    getIconSync(icon: IconName, options?: IconOptions): TrustedHtml;
}

const iconAttributes = {
    'aria-hidden': 'true',
    focusable: 'false'
};

const buildAttributesMarkup = (attributes: Record<string, JsonValue | null | undefined> | undefined): TrustedHtml => {
    if (!attributes) {
        return EMPTY_UI_HTML;
    }
    const normalizedAttributes: Record<string, UiAttributeValue> = {};
    for (const [name, rawValue] of Object.entries(attributes)) {
        if (rawValue == null || rawValue === false) {
            continue;
        }
        if (rawValue === true) {
            normalizedAttributes[name] = true;
            continue;
        }
        if (typeof rawValue !== 'string' && typeof rawValue !== 'number') {
            throw new Error(`UI attribute ${name} requires a primitive value`);
        }
        normalizedAttributes[name] = rawValue;
    }
    return uiAttributes(normalizedAttributes);
};

const formatLayoutClass = (contentLayout: 'collections' | 'card-grid' | 'sections' | 'analytics' | null): string => {
    if (contentLayout === 'collections') {
        return 'page-content-area--collections';
    }
    if (contentLayout === 'card-grid') {
        return 'page-content-area--collections page-content-area--card-grid';
    }
    if (contentLayout === 'sections') {
        return 'page-content-area--sections';
    }
    if (contentLayout === 'analytics') {
        return 'page-content-area--analytics';
    }
    return '';
};

const normalizeHtmlMarkup = (value: TrustedHtml | string | undefined): TrustedHtml => {
    if (!value) {
        return EMPTY_UI_HTML;
    }
    return isTrustedHtml(value) ? value : uiText(value);
};

const requireTrustedMarkupSlot = (value: TrustedHtml | string | undefined, slotName: string): TrustedHtml => {
    if (!value) {
        return EMPTY_UI_HTML;
    }
    if (!isTrustedHtml(value)) {
        throw new TypeError(`${slotName} must be TrustedHtml`);
    }
    return value;
};

const formatSelectionLabel = (prefix: string, optionLabel: string, standalone: boolean): string => {
    if (standalone) return optionLabel;
    return `${prefix} ${optionLabel.charAt(0).toLocaleLowerCase()}${optionLabel.slice(1)}`;
};

const buildFilterMarkup = (filter: FilterDefinition | undefined, actionClass = ''): TrustedHtml => {
    if (!filter) return EMPTY_UI_HTML;
    const shellActionClass = actionClass ? ` ${actionClass}` : '';
    if (filter.type === 'select' && filter.options) {
        const optionsMarkup = filter.options
            .map((option) => {
                const selectionLabel = filter.selectionPrefix ? formatSelectionLabel(filter.selectionPrefix, option.label, option.standaloneSelectionLabel === true) : option.label;
                return uiHtml`<option value="${uiAttr(option.value)}" data-selection-label="${uiAttr(selectionLabel)}"${option.selected ? staticUiHtml` selected` : EMPTY_UI_HTML}>${uiText(option.label)}</option>`.html;
            })
            .join('');
        const classValue = `page-header-filter-select${filter.id ? ` ${filter.id}` : ''}`;
        const prefixIconClass = filter.icon ? ' dropdown-select--prefix-icon' : '';
        const selectionPrefixClass = filter.selectionPrefix ? ' dropdown-select--selection-prefix' : '';
        const prefixIcon = filter.icon ? uiHtml`<span class="dropdown-select__prefix-icon" aria-hidden="true">${filter.icon}</span>` : EMPTY_UI_HTML;
        const selectedOption = filter.options.find((option) => option.selected) ?? filter.options[0];
        const selectionLabel = filter.selectionPrefix && selectedOption ? uiHtml`<span class="dropdown-select__selection-label" aria-hidden="true">${uiText(formatSelectionLabel(filter.selectionPrefix, selectedOption.label, selectedOption.standaloneSelectionLabel === true))}</span>` : EMPTY_UI_HTML;
        const idMarkup = uiAttributes({ id: filter.id });
        const attrsMarkup = buildAttributesMarkup({ ...filter.attributes, 'data-selection-prefix': filter.selectionPrefix });
        return toTrustedUiHtml(`<span class="dropdown-select page-header-filter-select-shell${prefixIconClass}${selectionPrefixClass}${uiAttr(shellActionClass).html}">${prefixIcon.html}${selectionLabel.html}<select class="${uiAttr(classValue).html}"${idMarkup.html}${attrsMarkup.html}>${optionsMarkup}</select></span>`);
    }
    if (filter.type === 'input') {
        const classValue = `page-header-filter-input${filter.id ? ` ${filter.id}` : ''}${shellActionClass}`;
        const inputAttributes = uiAttributes({ id: filter.id, placeholder: filter.placeholder });
        const attrsMarkup = buildAttributesMarkup(filter.attributes);
        return uiHtml`<input type="text" class="${uiAttr(classValue)}"${inputAttributes}${attrsMarkup}>`;
    }
    return requireTrustedMarkupSlot(filter.html, 'Header filter html');
};

const generateHeaderActionMarkup = (context: HeaderTemplateHost, definition: HeaderActionDefinition): TrustedHtml => {
    if (definition.type === 'search') {
        const idValue = `${context.pageId}-search-container`;
        const classValue = `page-header-search u-stretch${definition.class ? ` ${definition.class}` : ''}`;
        return uiHtml`<div id="${uiAttr(idValue)}" class="${uiAttr(classValue)}" role="search"></div>`;
    }
    if (definition.type === 'filter') {
        return buildFilterMarkup(definition.filter, definition.class ?? '');
    }
    if (definition.type === 'button') {
        const classValue = `ui-button${definition.variant ? ` ${definition.variant}` : ''}${definition.class ? ` ${definition.class}` : ''}`;
        const buttonAttributes = uiAttributes({ id: definition.id });
        const attrsMarkup = buildAttributesMarkup(definition.attributes);
        const contentMarkup = normalizeHtmlMarkup(definition.content);
        return uiHtml`<button type="button" class="${uiAttr(classValue)}"${buttonAttributes}${renderLabelAttributes(definition.ariaLabel)}${attrsMarkup}>${contentMarkup}</button>`;
    }
    return requireTrustedMarkupSlot(definition.html, 'Header custom action html');
};

const generateHeaderActionsMarkup = (context: HeaderTemplateHost, actions: HeaderActionDefinition[]): TrustedHtml => {
    if (!actions.length) {
        return EMPTY_UI_HTML;
    }
    const rendered = actions.map((action) => generateHeaderActionMarkup(context, action).html).join('');
    const triggerLabel = i18n.t('header.actions.moreActions');
    const triggerIcon = context.getIconSync('ellipsis', { size: 20, strokeWidth: 1.5 });
    return uiHtml`<div class="page-actions"><button type="button" class="ui-icon-button page-actions__trigger" aria-label="${uiAttr(triggerLabel)}" data-tooltip="${uiAttr(triggerLabel)}" aria-haspopup="true" aria-expanded="false">${renderIconSlot(triggerIcon)}</button><div class="page-actions__menu" role="toolbar">${toTrustedUiHtml(rendered)}</div></div>`;
};

const generateHeaderStatActionMarkup = (context: HeaderTemplateHost, action: HeaderStatActionDefinition): TrustedHtml => {
    const iconMarkup = action.icon ? normalizeHtmlMarkup(action.icon) : action.iconName ? context.getIconSync(action.iconName, { size: 14, strokeWidth: 1.5, attributes: iconAttributes }) : context.getIconSync('settings', { size: 14, strokeWidth: 1.5, attributes: iconAttributes });
    const iconContainer = iconMarkup.html ? renderIconSlot(iconMarkup) : EMPTY_UI_HTML;
    const toneClass = action.tone === 'primary' ? 'ui-round-button--copy' : action.tone === 'violet' ? 'ui-round-button--violet' : 'ui-round-button--settings';
    const attributes = uiAttributes({ id: action.buttonId, disabled: action.disabled === true });
    return uiHtml`<button type="button" class="ui-round-button ${uiAttr(toneClass)}"${attributes} data-action="${uiAttr(action.actionId)}" aria-label="${uiAttr(action.label)}" data-tooltip="${uiAttr(action.label)}">${iconContainer}</button>`;
};

const generateHeaderStatValueMarkup = (entry: HeaderStatDefinition): TrustedHtml => {
    const valueClass = `stat-value ${entry.id}`;
    if (!entry.inlineEdit) {
        return uiHtml`<div class="${uiAttr(valueClass)}" id="${uiAttr(entry.id)}">---</div>`;
    }
    const editor = entry.inlineEdit;
    return uiHtml`<div class="ui-inline-text-edit"><button type="button" class="${uiAttr(`${valueClass} ui-inline-text-edit__trigger`)}" id="${uiAttr(entry.id)}" data-action="${uiAttr(editor.startActionId)}" aria-label="${uiAttr(editor.editLabel)}" data-tooltip="${uiAttr(editor.editLabel)}">---</button><input type="text" class="ui-inline-text-edit__input u-hidden" id="${uiAttr(editor.inputId)}" aria-label="${uiAttr(editor.editLabel)}"><button type="button" class="ui-inline-text-edit__save ui-button ui-variant-accent u-hidden" data-action="${uiAttr(editor.saveActionId)}" aria-label="${uiAttr(editor.saveLabel)}" data-tooltip="${uiAttr(editor.saveLabel)}">${uiText(editor.saveLabel)}</button><button type="button" class="ui-inline-text-edit__cancel ui-button ui-variant-neutral u-hidden" data-action="${uiAttr(editor.cancelActionId)}" aria-label="${uiAttr(editor.cancelLabel)}" data-tooltip="${uiAttr(editor.cancelLabel)}">${uiText(editor.cancelLabel)}</button></div>`;
};

const generateHeaderStatsMarkup = (context: HeaderTemplateHost, stats: ReadonlyArray<HeaderStatDefinition>): TrustedHtml => {
    const entries = stats
        .map((entry) => {
            const actions = entry.actions ?? [];
            const hasAction = actions.length > 0;
            const actionButtons = hasAction ? uiHtml`<div class="ui-page-header-stats__card-action">${toTrustedUiHtml(actions.map((action) => generateHeaderStatActionMarkup(context, action).html).join(''))}</div>` : EMPTY_UI_HTML;
            const cardClass = `ui-page-header-stats__card${hasAction ? ' ui-page-header-stats__card--interactive' : ''}`;
            const valueMarkup = generateHeaderStatValueMarkup(entry);
            return uiHtml`<div class="${uiAttr(cardClass)}">${actionButtons}${valueMarkup}<div class="stat-label">${uiText(entry.label)}</div></div>`.html;
        })
        .join('');
    return entries ? toTrustedUiHtml(`<div class="ui-page-header-stats u-hide-mobile-portrait">${entries}</div>`) : EMPTY_UI_HTML;
};

const buildStandardHeaderMarkup = (context: HeaderTemplateHost, options: GenerateStandardHeaderOptions = {}): TrustedHtml => {
    const { containerClass: rawContainerClass = `${context.pageId}-container page-scrollable`, floating = true, detachedHeaderMode = 'hide', title = '', description = '', icon = null, actions = [], stats = [], toolbars = null, tabs = null, contentAreaClass = 'page-content-area', contentLayout = null, role = 'main', ariaLabel = null } = options;
    const routeRegistry = getRouteRegistry();
    const routeEntry = routeRegistry[context.pageId] ?? null;
    const resolvedIconMarkup = icon ? context.getIconSync(icon, { size: 22, strokeWidth: 1.5 }) : routeEntry?.sidebar?.icon ? context.getIconSync(routeEntry.sidebar.icon, { size: 22, strokeWidth: 1.5 }) : null;
    const containerClasses = new Set((rawContainerClass || '').split(/\s+/).filter(Boolean));
    containerClasses.add('content-container');
    if (contentLayout === 'card-grid' && containerClasses.has('page-scrollable')) {
        containerClasses.add('page-scrollable--card-grid');
    }
    const containerClass = `${Array.from(containerClasses).join(' ')}`;
    const contentClass = `${contentAreaClass}${floating ? ' page-content-area--floating' : ''} ${formatLayoutClass(contentLayout)}`.trim();
    const titleText = context.isDetached() ? `SoAI - ${title}` : title;
    const renderedStats = generateHeaderStatsMarkup(context, stats);
    const renderedActions = generateHeaderActionsMarkup(context, actions);
    const toolbarsMarkup = toolbars ? uiHtml`<div class="page-header-toolbars"${uiAttributes({ id: toolbars.id, 'aria-label': toolbars.ariaLabel })}${toolbars.ariaLabel ? staticUiHtml` role="group"` : EMPTY_UI_HTML}>${requireTrustedMarkupSlot(toolbars.html, 'Header toolbars html')}</div>` : EMPTY_UI_HTML;
    const tabsBody = tabs ? requireTrustedMarkupSlot(tabs.html, 'Header tabs html') : EMPTY_UI_HTML;
    const tabsMarkup = tabs ? uiHtml`<div class="page-header-tabs-container" id="${uiAttr(tabs.containerId || 'tabs-container')}">${tabsBody}</div>` : EMPTY_UI_HTML;
    const contentLabel = i18n.t('pageOutlet.contentLabel');
    const panelClass = `page-header-panel ${floating ? 'is-floating' : 'is-static'}`;
    const iconContainer = resolvedIconMarkup ? uiHtml`<div class="page-header-icon">${resolvedIconMarkup}</div>` : EMPTY_UI_HTML;
    const titleMarkup = buildPageHeaderTitleMarkup(titleText);
    const ariaMarkup = uiAttributes({ 'aria-label': ariaLabel });
    const shouldRenderHeader = !(context.isDetached() && detachedHeaderMode === 'hide');
    const headerMarkup = shouldRenderHeader ? uiHtml`<div class="${uiAttr(panelClass)}"><div class="page-header" role="banner"><div class="page-header-title-section">${iconContainer}<div class="page-header-copy">${titleMarkup}<p class="page-header-description">${uiText(description)}</p></div></div>${renderedActions}</div>${toolbarsMarkup}${renderedStats}${tabsMarkup}</div>` : EMPTY_UI_HTML;
    const contentMarkup = uiHtml`<div class="${uiAttr(contentClass)}" role="region" aria-label="${uiAttr(contentLabel)}"><!-- Page content goes here --></div>`;
    return uiHtml`<div class="${uiAttr(containerClass)}" data-section="${uiAttr(context.pageId)}" data-page-transition-surface="true" role="${uiAttr(role)}"${ariaMarkup}>${headerMarkup}${contentMarkup}</div>`;
};

const buildHeaderStatsMarkup = (context: HeaderTemplateHost, stats: ReadonlyArray<HeaderStatDefinition>): TrustedHtml => generateHeaderStatsMarkup(context, stats);

export { buildHeaderStatsMarkup, buildStandardHeaderMarkup, buildFilterMarkup };
export type { HeaderTemplateHost };
