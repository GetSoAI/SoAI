/* SoAI - Models feature provider creation [frontend/assets/ts/features/models/modals/downloadmodal/manager/actions/providerCreation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { splitTrimmedList, toTrimmedString } from '@core/normalize.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { closeDownloadModelModal } from '@features/models/modals/downloadmodal/manager/view.ts';
import { locatePluginByName } from '@features/models/modals/downloadmodal/pluginAvailability.ts';

const createExternalProvider = async (runtime: DownloadModalManagerRuntime): Promise<void> => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const plugin = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'provider-plugin-select'), 'Download modal provider-plugin-select', modalRoot).value);
    const name = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'provider-name'), 'Download modal provider-name', modalRoot).value);
    const url = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'provider-api-url'), 'Download modal provider-api-url', modalRoot).value);
    const key = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'provider-api-key'), 'Download modal provider-api-key', modalRoot).value);
    const filter = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'provider-models-filter'), 'Download modal provider-models-filter', modalRoot).value);
    if (!plugin) {
        runtime.host.session.showNotification(i18n.t('models.notifications.selectPlugin'), 'error');
        return;
    }
    if (!name) {
        runtime.host.session.showNotification(i18n.t('models.notifications.enterProviderName'), 'error');
        return;
    }
    if (!url) {
        runtime.host.session.showNotification(i18n.t('models.notifications.enterApiUrl'), 'error');
        return;
    }
    if (!key) {
        runtime.host.session.showNotification(i18n.t('models.notifications.enterApiKey'), 'error');
        return;
    }
    const pluginEntry = locatePluginByName(runtime.host, plugin);
    if (!pluginEntry || !runtime.host.catalog.isProviderPluginOperational(pluginEntry)) {
        runtime.host.session.showNotification(i18n.t('models.notifications.pluginUnavailable'), 'error');
        return;
    }
    const payload: { name: string; apiUrl: string; apiKey: string; modelsFilter?: string[] } = {
        name,
        apiUrl: url,
        apiKey: key
    };
    if (filter) {
        payload.modelsFilter = splitTrimmedList(filter, ',');
    }
    const confirmButton = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'confirm-download'), modalRoot);
    const disableTargets = [runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-plugin-select'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-name'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-api-url'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-api-key'), modalRoot), runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-models-filter'), modalRoot)];
    runtime.state.isCreatingProvider = true;
    runtime.host.view.setButtonLoading(confirmButton, true, {
        loadingText: i18n.t('models.modal.addProvider.confirmProvider'),
        idleText: i18n.t('models.modal.addProvider.confirmProvider'),
        disableTargets
    });
    try {
        await runtime.host.session.api.plugins.providers.add(plugin, payload);
        runtime.state.acceptedCatalogMutation = true;
        runtime.host.session.showNotification(i18n.t('models.notifications.providerCreateSuccess', { provider: name }), 'success');
        closeDownloadModelModal(runtime);
        await runtime.host.catalog.loadPlugins({ force: true });
        runtime.host.catalog.updateProviderButtonVisibility();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadModalController', 'Failed to create external provider', runtimeError);
        runtime.host.session.showNotification(i18n.t('models.notifications.providerCreateFailed'), 'error');
    } finally {
        runtime.state.isCreatingProvider = false;
        runtime.host.view.setButtonLoading(confirmButton, false, {
            loadingText: i18n.t('models.modal.addProvider.confirmProvider'),
            idleText: i18n.t('models.modal.addProvider.confirmProvider'),
            disableTargets
        });
    }
};

export { createExternalProvider };
