/* SoAI - Download modal variant probe events [frontend/assets/ts/features/models/modals/downloadmodal/manager/variantEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireInputElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';
import { scrollDownloadModalSectionIntoView } from '@features/models/modals/downloadmodal/manager/scrolling.ts';

const handleVariantCheck = async (runtime: DownloadModalManagerRuntime, _event?: Event): Promise<void> => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const resolver = createModalElementResolver(modalRoot, 'Download modal');
    const plugin = toTrimmedString(requireSelectElement(resolver, modalUiSelector(modalId, 'download-plugin-select'), 'Download modal download-plugin-select', modalRoot).value);
    const modelId = toTrimmedString(requireInputElement(resolver, modalUiSelector(modalId, 'model-id'), 'Download modal model-id', modalRoot).value);
    if (!plugin || !modelId) {
        return;
    }

    const token = runtime.host.execution.variantProbe.prepareForProbe();
    runtime.host.execution.variantProbe.enableVariantFilter();
    runtime.host.execution.variantProbe.showCheckingStatus();

    try {
        const variants = await runtime.host.execution.modelActions.probeModelVariants(plugin, modelId);
        if (!runtime.host.execution.variantProbe.isTokenActive(token)) {
            return;
        }
        runtime.host.execution.variantProbe.handleSuccess(token, variants);
        scrollDownloadModalSectionIntoView(runtime, 'model-variant-results');
    } catch (error) {
        if (!runtime.host.execution.variantProbe.isTokenActive(token)) {
            return;
        }
        const runtimeError = ensureError(error);
        errorHandler.error('DownloadModalController', 'Failed to probe model variants', runtimeError);
        const message = runtime.host.execution.variantProbe.buildErrorMessage(runtimeError) ?? i18n.t('models.modal.addModel.variantCheck.error');
        runtime.host.execution.variantProbe.handleFailure(token, message);
    }
};

export { handleVariantCheck };
