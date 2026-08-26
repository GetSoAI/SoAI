/* SoAI - Settings feature external account modal [frontend/assets/ts/features/settings/externalaccounts/externalAccountModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireModalPresenter, type ModalDefinition } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { createExternalAccountModalElement } from '@features/settings/externalaccounts/externalAccountModalView.ts';
import { initializeExternalAccountModalSession } from '@features/settings/externalaccounts/externalAccountModalSession.ts';
import type { ExternalAccountModalOpenOptions } from '@features/settings/externalaccounts/externalAccountModalTypes.ts';

const SETTINGS_EXTERNAL_ACCOUNT_MODAL_ID = 'settings-external-account-modal';

const externalAccountModalDefinition: ModalDefinition = {
    id: SETTINGS_EXTERNAL_ACCOUNT_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(SETTINGS_EXTERNAL_ACCOUNT_MODAL_ID, 'choose-mail'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createExternalAccountModalElement(SETTINGS_EXTERNAL_ACCOUNT_MODAL_ID)
};

const openExternalAccountModal = async (options: ExternalAccountModalOpenOptions): Promise<void> => {
    const presenter = requireModalPresenter();
    await runModalSession<void>({
        presenter,
        modalId: SETTINGS_EXTERNAL_ACCOUNT_MODAL_ID,
        onAlreadyOpen: 'replace',
        initialResult: undefined,
        initialize: (context) => initializeExternalAccountModalSession(context, presenter, SETTINGS_EXTERNAL_ACCOUNT_MODAL_ID, options)
    });
};

export { SETTINGS_EXTERNAL_ACCOUNT_MODAL_ID, externalAccountModalDefinition, openExternalAccountModal };
