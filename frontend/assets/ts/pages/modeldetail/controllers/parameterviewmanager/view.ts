/* SoAI - Model detail page control layer parameter view manager rendering [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes } from '@core/security/labelAttributes.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import { ACTION_EDIT_VIRTUAL_MODEL } from '@features/modeldetail/public.ts';
import type { ParameterTemplateOptions } from '@pages/modeldetail/contracts/parameterTypes.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import type { ParameterViewHost } from '@pages/modeldetail/controllers/parameterviewmanager/types.ts';
import { requireConfiguredIcon } from '@pages/modeldetail/guards/guards.ts';
import { renderParametersView } from '@pages/modeldetail/widgets/parametertemplates/view.ts';

const createTemplateOptions = (state: ParameterStateManager, icons: Record<string, TrustedHtml>): ParameterTemplateOptions => {
    const isCustomized: ParameterTemplateOptions['isCustomized'] = (parameter): boolean => {
        if (isString(parameter)) {
            return state.isParameterCustomized(parameter);
        }
        if (isObject(parameter) && isString(parameter.key)) {
            return state.isParameterCustomized(parameter.key);
        }
        return false;
    };
    return {
        categories: state.categories,
        icons,
        isCustomized,
        describeArray: (itemType?: string): string => i18n.t('modelDetail.parameters.arrayOfType', { itemType: itemType ?? '' })
    };
};

const resolveVirtualModelStrategyLabel = (strategy: string): string => {
    const normalized = strategy.trim().toLowerCase();
    switch (normalized) {
        case 'load_balancing':
            return i18n.t('models.strategies.load_balancing');
        case 'failover':
            return i18n.t('models.strategies.failover');
        default:
            return i18n.t('common.unknown');
    }
};

const renderBackendDocumentationLayout = (icon: TrustedHtml): string => {
    const label = i18n.t('modelDetail.buttons.backend_documentation');
    return `<div class="model-parameter-layout">
        <div class="model-parameter-section parameter-category parameter-category--backend-doc glass-surface-full glass-surface-medium">
            <div class="card-title-bar modeldetail-category-header">
                <h3 class="card-title category-title">${i18n.t('modelDetail.parameters.backendDocumentationTitle')}</h3>
            </div>
            <div class="category-content has-scroll">
                <div class="model-parameter-doc-callout">
                    <p class="model-parameter-doc-description">${i18n.t('modelDetail.parameters.backendDocumentationDescription')}</p>
                    <a class="ui-button ui-button--sm" id="backend-doc-button" data-action="backend-documentation" target="_blank" rel="noopener noreferrer" aria-disabled="true" tabindex="-1">${icon.html}<span>${label}</span></a>
                </div>
            </div>
        </div>
    </div>`;
};

const renderVirtualModel = (host: ParameterViewHost, container: Element, model: ModelRecord | null): void => {
    const strategy = model?.strategy ?? 'load_balancing';
    const models = Array.isArray(model?.models) ? model.models : [];

    const rows =
        models
            .map((entry) => {
                const record = isObject(entry) ? entry : null;
                const nameCandidate = record?.['name'] ?? record?.['id'] ?? record?.['universalId'] ?? '';
                const name = isString(nameCandidate) ? nameCandidate : String(nameCandidate ?? '');
                const uidCandidate = record?.['universalId'] ?? record?.['id'] ?? name;
                const uid = isString(uidCandidate) ? uidCandidate : String(uidCandidate ?? '');
                const parameters = record?.['parameters'];
                const hasParameters = isObject(parameters) && Object.keys(parameters).length > 0;
                const badge = hasParameters ? `<span class="param-badge custom">${i18n.t('modelDetail.cards.constituents.hasParameters')}</span>` : '';
                return `
                    <div class="constituent-item">
                        <div><strong>${securityApi.escapeHtml(name)}</strong></div>
                        <div class="stat-row"><span class="stat-label">${securityApi.escapeHtml(i18n.t('common.uid'))}</span><span class="stat-value">${securityApi.escapeHtml(uid)}</span></div>
                        ${badge}
                    </div>`;
            })
            .join('') || `<div class="ui-empty-state--simple">${i18n.t('modelDetail.cards.constituents.noModels')}</div>`;

    const viewMarkup = toTrustedUiHtml(`
                <div class="parameters-content">
                    <div class="modeldetail-overview-card-content">
                        <div class="stat-row"><span class="stat-label">${i18n.t('modelDetail.cards.virtualModelInfo.strategy')}</span><span class="stat-value">${resolveVirtualModelStrategyLabel(String(strategy))}</span></div>
                        <div class="stat-row"><span class="stat-label">${i18n.t('modelDetail.cards.virtualModelInfo.constituentCount')}</span><span class="stat-value">${models.length}</span></div>
                    </div>
                    <div class="constituent-list">${rows}</div>
                    <div class="virtual-model-edit">
                        <button type="button" class="ui-button ui-variant-warning" id="edit-virtual-model-btn" data-action="${ACTION_EDIT_VIRTUAL_MODEL}" ${renderLabelAttributes(i18n.t('models.actions.editVirtualModel'))}>${i18n.t('models.actions.editVirtualModel')}</button>
                    </div>
                </div>`);
    host.pageDom.updateHtml(container, viewMarkup);
};

const renderNoParameters = (host: ParameterViewHost, container: Element, icons: Record<string, TrustedHtml>): void => {
    const icon = requireConfiguredIcon(icons, 'PARAMETERS', { subject: 'ParameterViewManager', verb: 'requires' });
    const documentationIcon = requireConfiguredIcon(icons, 'BACKEND_DOCUMENTATION', { subject: 'ParameterViewManager', verb: 'requires' });
    const emptyParametersMarkup = toTrustedUiHtml(`<div class="parameters-content" id="parameters-scroll">${renderBackendDocumentationLayout(documentationIcon)}<div class="no-parameters u-flex-center-col">${icon.html}<p>${i18n.t('modelDetail.parameters.noParameters')}</p></div></div>`);
    host.pageDom.updateHtml(container, emptyParametersMarkup);
};

const renderParameters = (host: ParameterViewHost, state: ParameterStateManager, container: Element, templateOptions: ParameterTemplateOptions): void => {
    const icon = host.getIconSync('search', { size: 48, strokeWidth: 1.5 });
    const emptyState = renderEmptyState({
        icon,
        title: i18n.t('modelDetail.parameters.noMatchTitle'),
        message: i18n.t('modelDetail.parameters.noMatchDescription')
    });
    const parametersMarkup = toTrustedUiHtml(`<div class="parameters-content" id="parameters-scroll"><div id="modeldetail-parameters-empty" class="u-hidden modeldetail-parameters-empty">${emptyState.html}</div>${renderParametersView(state.parameters, templateOptions)}</div>`);
    host.pageDom.updateHtml(container, parametersMarkup);
};

export { createTemplateOptions, renderNoParameters, renderParameters, renderVirtualModel };
