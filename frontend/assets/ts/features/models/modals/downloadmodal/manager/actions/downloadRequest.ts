/* SoAI - Models feature download request [frontend/assets/ts/features/models/modals/downloadmodal/manager/actions/downloadRequest.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { splitModelVariantInput } from '@core/modelactions/variantInput.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { locatePluginByName } from '@features/models/modals/downloadmodal/pluginAvailability.ts';

const buildDownloadRequest = (
    runtime: DownloadModalManagerRuntime
): {
    plugin?: string;
    modelId?: string;
    universalId?: string;
    quantization?: string;
} | null => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const plugin = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value);
    const rawId = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-id'), 'Download modal model-id', modalRoot).value);
    let quant = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-quant'), 'Download modal model-quant', modalRoot).value);
    if (!rawId) {
        runtime.host.session.showNotification(i18n.t('models.notifications.enterModelId'), 'error');
        return null;
    }
    let modelId = rawId;
    let universalId: string | null = null;
    if (plugin) {
        const parsed = splitModelVariantInput(rawId);
        if (parsed.variantToken) {
            modelId = parsed.modelId;
            quant = parsed.variantToken;
        }
    } else {
        universalId = rawId;
    }
    if (!universalId && !plugin) {
        runtime.host.session.showNotification(i18n.t('models.notifications.selectPlugin'), 'error');
        return null;
    }
    if (plugin) {
        const pluginEntry = locatePluginByName(runtime.host, plugin);
        if (!pluginEntry || !runtime.host.catalog.isDownloadPluginOperational(pluginEntry)) {
            runtime.host.session.showNotification(i18n.t('models.notifications.pluginUnavailable'), 'error');
            return null;
        }
    }
    const quantization = quant ? quant : undefined;
    if (universalId) {
        return quantization ? { universalId, quantization } : { universalId };
    }
    return quantization ? { plugin, modelId, quantization } : { plugin, modelId };
};

export { buildDownloadRequest };
