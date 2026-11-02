/* SoAI - Messaging editor live model catalog projection [frontend/assets/ts/features/settings/messaging/modalCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { ModelCatalogReadController } from '@core/models/ModelCatalogReadController.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { showUserWarning } from '@core/ui/notifications/notifications.ts';
import { clearStatusSurface, setStatusSurface } from '@core/ui/statusSurface.ts';
import { SETTINGS_MESSAGING_ACCOUNT_MODAL_ID } from '@features/settings/messaging/constants.ts';
import { populateMessagingModels } from '@features/settings/messaging/modalFormState.ts';
import { buildMessagingModelOptions } from '@features/settings/messaging/modelOptions.ts';
import type { MessagingAccountModalOptions } from '@features/settings/messaging/types.ts';

const mountMessagingModelCatalog = (modal: HTMLElement, options: MessagingAccountModalOptions, signal: AbortSignal, changed: () => void): (() => void) => {
    const select = dom.resolve(modalUiSelector(SETTINGS_MESSAGING_ACCOUNT_MODAL_ID, 'model'), modal);
    const status = dom.resolve(modalUiSelector(SETTINGS_MESSAGING_ACCOUNT_MODAL_ID, 'model-catalog-status'), modal);
    if (!(select instanceof HTMLSelectElement) || !(status instanceof HTMLElement)) throw new Error('Messaging model catalog controls are missing');
    let failureShown = false;
    const projectUnavailable = (): void => {
        populateMessagingModels(select, options.models, readTrimmedSelectValue(select), false);
        setStatusSurface({ surface: status, message: i18n.t('settings.messaging.modelCatalog.unavailable'), tone: 'warning', visibility: 'hiddenAttribute' });
        changed();
    };
    const catalog = new ModelCatalogReadController({
        owner: options.owner,
        signal,
        subscribeCatalog: options.subscribeModelCatalog,
        readCatalog: async (signal, timeoutMs) => buildMessagingModelOptions(await options.loadModelCatalog({ signal, timeoutMs })),
        applyCatalog: (models) => {
            if (models === null) return projectUnavailable();
            options.models = models;
            populateMessagingModels(select, models, readTrimmedSelectValue(select));
            clearStatusSurface(status, 'hiddenAttribute');
            failureShown = false;
            changed();
        },
        reportFailure: (error) => {
            projectUnavailable();
            if (failureShown) return;
            failureShown = true;
            errorHandler.warn('MessagingModelCatalog', 'Model catalog reconciliation failed', error);
            showUserWarning(i18n.t('settings.messaging.modelCatalog.unavailable'));
        }
    });
    try {
        projectUnavailable();
        catalog.start();
        terminateHandledPromise(catalog.ensureReady());
    } catch (error) {
        const failures: Error[] = [ensureError(error)];
        runCleanupStepCollectingFailure(() => catalog.stop(), failures);
        throwCollectedCleanupFailures(failures);
    }
    return () => catalog.stop();
};

export { mountMessagingModelCatalog };
