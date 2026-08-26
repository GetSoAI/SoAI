/* SoAI - Settings page external accounts manager [frontend/assets/ts/pages/settings/controllers/page/externalAccountsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ExternalAccountsManager } from '@features/settings/public.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { hasSearchQuery } from '@pages/settings/controllers/page/hostBindings.ts';

const createExternalAccountsManager = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): void => {
    state.externalAccountsManager = new ExternalAccountsManager({
        host: {
            api: page.owners.api,
            pageDom: page.owners.pageDom,
            pageResources: page.owners.pageResources,
            feedback: page.owners.feedback,
            runWithBoundary: <T>(name: string, task: () => Promise<T> | T): Promise<T> => page.owners.pageLifecycle.run(name, task),
            withButtonDisabled: callbacks.withButtonDisabled,
            confirmAndExecute: callbacks.confirmAndExecute,
            hasSearchQuery: (): boolean => hasSearchQuery(page),
            filterSettings: callbacks.filterSettings
        }
    });
};

export { createExternalAccountsManager };
