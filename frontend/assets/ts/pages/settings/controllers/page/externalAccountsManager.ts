/* SoAI - Settings page external accounts manager [frontend/assets/ts/pages/settings/controllers/page/externalAccountsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ExternalAccountsManager } from '@features/settings/public.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { buildBaseHostBindings } from '@pages/settings/controllers/page/hostBindings.ts';

const createExternalAccountsManager = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): void => {
    const baseBindings = buildBaseHostBindings(page, callbacks);
    state.externalAccountsManager = new ExternalAccountsManager({
        host: {
            ...baseBindings,
            api: page.owners.api,
            withButtonDisabled: callbacks.withButtonDisabled,
            confirmAndExecute: callbacks.confirmAndExecute
        }
    });
};

export { createExternalAccountsManager };
