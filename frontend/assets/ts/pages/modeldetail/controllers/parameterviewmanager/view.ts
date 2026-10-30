/* SoAI - Model detail page control layer parameter view manager rendering [frontend/assets/ts/pages/modeldetail/controllers/parameterviewmanager/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { reconcileElementChildrenFromTrustedHtml } from '@core/dom/childNodeReconciliation.ts';
import { getSelectDefaultValue, setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
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
import { renderBackendDocumentation, renderParametersView } from '@pages/modeldetail/widgets/parametertemplates/view.ts';

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

const renderNoParameters = (host: ParameterViewHost, container: Element, templateOptions: ParameterTemplateOptions): void => {
    const icon = requireConfiguredIcon(templateOptions.icons, 'PARAMETERS', { subject: 'ParameterViewManager', verb: 'requires' });
    const emptyParametersMarkup = toTrustedUiHtml(`<div class="parameters-content" id="parameters-scroll">${renderBackendDocumentation(templateOptions)}<div class="no-parameters u-flex-center-col">${icon.html}<p>${i18n.t('modelDetail.parameters.noParameters')}</p></div></div>`);
    host.pageDom.updateHtml(container, emptyParametersMarkup);
};

const renderParameters = (host: ParameterViewHost, state: ParameterStateManager, container: Element, templateOptions: ParameterTemplateOptions): void => {
    const emptyState = renderEmptyState({
        icon: host.getIconSync('search', { size: 48, strokeWidth: 1.5 }),
        title: i18n.t('modelDetail.parameters.noMatchTitle'),
        message: i18n.t('modelDetail.parameters.noMatchDescription')
    });
    const parametersMarkup = toTrustedUiHtml(`<div class="parameters-content" id="parameters-scroll">${renderParametersView(state.parameters, templateOptions, emptyState.html)}</div>`);
    reconcileElementChildrenFromTrustedHtml({ target: container, html: parametersMarkup });
    for (const control of dom.resolveAll('input[data-param], textarea[data-param], select[data-param]', container)) {
        if (control instanceof HTMLInputElement) {
            if (control.type === 'checkbox') control.checked = control.defaultChecked;
            else if (control.value !== control.defaultValue) control.value = control.defaultValue;
        } else if (control instanceof HTMLTextAreaElement) {
            if (control.value !== control.defaultValue) control.value = control.defaultValue;
        } else if (control instanceof HTMLSelectElement) {
            setSelectValueAndSyncDefault(control, getSelectDefaultValue(control));
        }
    }
};

export { createTemplateOptions, renderNoParameters, renderParameters, renderVirtualModel };
