/* SoAI - Model download confirmation action ownership [frontend/assets/ts/features/models/modals/downloadmodal/manager/actions/confirmAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createExternalProvider } from '@features/models/modals/downloadmodal/manager/actions/providerCreation.ts';
import { downloadModel } from '@features/models/modals/downloadmodal/manager/actions/downloadStreams.ts';
import type { DownloadModalManagerRuntime } from '@features/models/modals/downloadmodal/manager/contracts.ts';

const handleConfirmAction = (runtime: DownloadModalManagerRuntime, _event?: Event): void => {
    const modalId = runtime.modalId;
    const modalRoot = runtime.host.session.modals.requireElement(modalId);
    const providerTab = runtime.host.session.requireHTMLElement(modalUiSelector(modalId, 'provider-tab'), modalRoot);
    if (runtime.host.session.dom.hasClass(providerTab, CSS_CLASSES.ACTIVE)) {
        if (runtime.state.isCreatingProvider) {
            return;
        }
        terminateHandledPromise(createExternalProvider(runtime));
        return;
    }
    terminateHandledPromise(downloadModel(runtime));
};

export { handleConfirmAction };
