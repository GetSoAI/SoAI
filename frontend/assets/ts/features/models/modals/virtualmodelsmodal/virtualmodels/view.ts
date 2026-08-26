/* SoAI - Virtual model modal rendering [frontend/assets/ts/features/models/modals/virtualmodelsmodal/virtualmodels/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { VIRTUAL } from '@core/realtime/streammanager/resources/ids.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { MODELS_VIRTUAL_MODELS_MODAL_ID, VIRTUAL_MODELS_MODAL_ACTION_DELETE, VIRTUAL_MODELS_MODAL_ACTION_EDIT } from '@features/models/modals/constants.ts';
import { normalizeVirtualModelsPayload } from '@features/models/modals/virtualmodelsmodal/virtualmodels/mappers.ts';
import type { VirtualModelsHost, VirtualModelsPrimaryTab, VirtualModelState } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

const VIRTUAL_MODELS_MODAL_ID = MODELS_VIRTUAL_MODELS_MODAL_ID;

interface LoadVirtualModelsListDependencies {
    host: VirtualModelsHost;
    state: VirtualModelState;
    clearVirtualModelsSubscription(): void;
    updateVirtualTabControls(): void;
    updateVirtualTabs(active: VirtualModelsPrimaryTab): void;
}

const getStrategyClassName = (strategy: string): string => {
    if (strategy === 'load_balancing') {
        return 'strategy-label strategy-label--load-balancing';
    }
    if (strategy === 'failover') {
        return 'strategy-label strategy-label--failover';
    }
    throw new Error(`Unsupported virtual model strategy: ${strategy}`);
};

const loadVirtualModelsList = (dependencies: LoadVirtualModelsListDependencies): void => {
    dependencies.clearVirtualModelsSubscription();
    const modalRoot = dependencies.host.view.modals.requireElement(VIRTUAL_MODELS_MODAL_ID);
    const container = dependencies.host.view.requireHTMLElement(modalUiSelector(VIRTUAL_MODELS_MODAL_ID, 'virtual-models-list'), modalRoot);
    const sanitizer = dependencies.host.view.sanitizer;
    dependencies.host.view.updateHTML(container, uiHtml`<div class="loading-container"><div class="loading-spinner"></div><span>${i18n.t('models.loading.providers')}</span></div>`);
    const render = (payload: JsonValue | null | undefined): void => {
        const list = normalizeVirtualModelsPayload(payload);
        dependencies.state.virtualModelCache = list;
        dependencies.state.virtualModelCount = list.length;
        dependencies.updateVirtualTabControls();
        if (!dependencies.state.virtualModelCount) {
            dependencies.updateVirtualTabs('create');
            dependencies.host.view.updateHTML(container, uiHtml`<div class="ui-empty-state--simple">${i18n.t('models.modal.virtualModels.noModels')}</div>`);
            return;
        }
        const editLabel = i18n.t('common.edit');
        const deleteLabel = i18n.t('common.delete');
        const deleteIcon = getIconSync('close', { strokeWidth: 1.5 }).html;
        const editIcon = getIconSync('model-config', { strokeWidth: 1 }).html;
        const markup = dependencies.state.virtualModelCache
            .map((virtualModel) => {
                const strategyLabel = dependencies.host.preferences.formatStrategyLabel(virtualModel.strategy) || virtualModel.strategy;
                const strategyClassName = getStrategyClassName(virtualModel.strategy);
                const count = virtualModel.models.length;
                const constituentLabel = i18n.plural('models.metrics.constituentModelsShortCount', count, {});
                const vmName = virtualModel.name;
                return `<div class="provider-item"><div class="provider-info"><div class="provider-name">${sanitizer.html(vmName)}</div><div class="provider-extra"><span class="${strategyClassName}">${sanitizer.html(strategyLabel)}</span> • ${count} ${sanitizer.html(constituentLabel)}</div></div><div class="ui-collection-card__action-bar"><button type="button" class="ui-round-button ui-round-button--delete" data-action="${VIRTUAL_MODELS_MODAL_ACTION_DELETE}" data-vm-name="${sanitizer.attribute(vmName)}" aria-label="${sanitizer.attribute(deleteLabel)}" data-tooltip="${sanitizer.attribute(deleteLabel)}">${deleteIcon}</button><button type="button" class="ui-round-button ui-round-button--edit" data-action="${VIRTUAL_MODELS_MODAL_ACTION_EDIT}" data-vm-name="${sanitizer.attribute(vmName)}" aria-label="${sanitizer.attribute(editLabel)}" data-tooltip="${sanitizer.attribute(editLabel)}">${editIcon}</button></div></div>`;
            })
            .join('');
        const modelMarkup = toTrustedUiHtml(markup);
        dependencies.host.view.updateHTML(container, modelMarkup);
    };
    const unsubscribe = dependencies.host.data.requireStreamSubscriptions().subscribeResourceState(
        VIRTUAL,
        (snapshot: ResourceSnapshot) => {
            if (snapshot.status === 'error') {
                errorHandler.error('VirtualModelsController', 'Virtual models stream error', snapshot.error);
                dependencies.state.virtualModelCache = [];
                dependencies.state.virtualModelCount = 0;
                dependencies.updateVirtualTabControls();
                dependencies.updateVirtualTabs('create');
                dependencies.host.view.updateHTML(container, uiHtml`<div class="ui-empty-state--simple">${i18n.t('models.modal.virtualModels.loadFailed')}</div>`);
                return;
            }
            try {
                if (snapshot.status !== 'ready') {
                    return;
                }
                render(snapshot.value);
            } catch (error) {
                errorHandler.error('VirtualModelsController', 'Virtual models payload invalid', ensureError(error));
                dependencies.state.virtualModelCache = [];
                dependencies.state.virtualModelCount = 0;
                dependencies.updateVirtualTabControls();
                dependencies.updateVirtualTabs('create');
                dependencies.host.view.updateHTML(container, uiHtml`<div class="ui-empty-state--simple">${i18n.t('models.modal.virtualModels.loadFailed')}</div>`);
            }
        },
        { immediate: true, ensureStart: true }
    );
    dependencies.state.subscription = { unsubscribe };
};

export { loadVirtualModelsList };
export type { LoadVirtualModelsListDependencies };
