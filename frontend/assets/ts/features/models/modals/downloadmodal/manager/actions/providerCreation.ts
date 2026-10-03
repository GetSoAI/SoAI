/* SoAI - Models feature provider creation [frontend/assets/ts/features/models/modals/downloadmodal/manager/actions/providerCreation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { closeDownloadModelModal } from '@features/models/modals/downloadmodal/manager/view.ts';
import { locatePluginByName } from '@features/models/modals/downloadmodal/pluginAvailability.ts';
import { submitProviderForm, validateProviderForm } from '@features/models/providerform/providerSubmission.ts';

const createExternalProvider = async (runtime: DownloadModalManagerRuntime): Promise<void> => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const readValue = (token: string): string => requireInputElement(resolver, modalUiSelector(modalId, token), `Download modal ${token}`, modalRoot).value;
    const validation = validateProviderForm(
        {
            pluginName: requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot).value,
            name: readValue('provider-name'),
            apiUrl: readValue('provider-api-url'),
            apiKey: readValue('provider-api-key'),
            modelsFilter: readValue('provider-models-filter')
        },
        { getPluginByName: (name) => locatePluginByName(runtime.host, name), isProviderPluginOperational: (plugin) => runtime.host.catalog.isProviderPluginOperational(plugin) }
    );
    if (validation.status === 'invalid') {
        runtime.host.session.showNotification(validation.message, 'error');
        return;
    }
    const name = validation.payload.name;
    const confirmButton = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'confirm-download'), modalRoot);
    const disableTargets = [runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-plugin-select'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-name'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-api-url'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-api-key'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-models-filter'), modalRoot)];
    const discoveryAbort = new AbortController();
    runtime.state.providerDiscoveryAbort = discoveryAbort;
    runtime.state.isCreatingProvider = true;
    runtime.host.view.setButtonLoading(confirmButton, true, {
        loadingText: i18n.t('models.modal.addProvider.confirmProvider'),
        idleText: i18n.t('models.modal.addProvider.confirmProvider'),
        disableTargets
    });
    try {
        const outcome = await submitProviderForm({
            pluginName: validation.pluginName,
            payload: validation.payload,
            signal: discoveryAbort.signal,
            addProvider: (pluginName, payload) => runtime.host.session.api.plugins.providers.add(pluginName, payload),
            waitForModelCatalogChange: (signal) => runtime.host.execution.waitForModelCatalogChange(signal),
            onAccepted: () => {
                if (!discoveryAbort.signal.aborted) {
                    runtime.state.acceptedCatalogMutation = true;
                }
                runtime.host.session.showNotification(i18n.t('models.notifications.providerCreateSuccess', { provider: name }), 'success');
                runtime.host.view.setButtonLoading(confirmButton, true, {
                    loadingText: i18n.t('models.loading.models'),
                    idleText: i18n.t('models.modal.addProvider.confirmProvider'),
                    disableTargets
                });
            }
        });
        if (outcome.status === 'failed') {
            if (!outcome.accepted) runtime.host.session.showNotification(i18n.t('models.notifications.providerCreateFailed'), 'error');
            return;
        }
        try {
            if (!discoveryAbort.signal.aborted && runtime.host.session.modals.isOpen(modalId)) {
                closeDownloadModelModal(runtime);
            }
        } catch (error) {
            errorHandler.error('DownloadModalController', 'Provider was created but post-accept processing failed', ensureError(error));
            return;
        }
        try {
            await runtime.host.catalog.loadPlugins({ force: true });
            runtime.host.catalog.updateProviderButtonVisibility();
        } catch (error) {
            errorHandler.error('DownloadModalController', 'Provider was created but the plugin catalog refresh failed', ensureError(error));
        }
    } finally {
        discoveryAbort.abort();
        if (runtime.state.providerDiscoveryAbort === discoveryAbort) {
            runtime.state.providerDiscoveryAbort = null;
        }
        runtime.state.isCreatingProvider = false;
        runtime.host.view.setButtonLoading(confirmButton, false, {
            loadingText: i18n.t('models.modal.addProvider.confirmProvider'),
            idleText: i18n.t('models.modal.addProvider.confirmProvider'),
            disableTargets
        });
    }
};

export { createExternalProvider };
