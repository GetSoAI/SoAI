/* SoAI - Settings page SoAI Connect manager [frontend/assets/ts/pages/settings/controllers/page/connectManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation } from '@core/environment/public.ts';
import { ConnectManager } from '@pages/settings/controllers/ConnectManager.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { buildBaseHostBindings } from '@pages/settings/controllers/page/hostBindings.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const createConnectManager = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): void => {
    const baseBindings = buildBaseHostBindings(page, callbacks);
    state.connectManager = new ConnectManager({
        pairing: {
            load: (options) => page.owners.api.system.connectPairing(options)
        },
        page: {
            readBrowserOrigin: () => {
                const location = getLocation();
                return { protocol: location.protocol, hostname: location.hostname, port: location.port };
            },
            notify: (message, type, duration) => page.owners.feedback.show(message, type, duration)
        },
        view: {
            requireContainer: () => page.owners.pageDom.require('connect-content'),
            updateHtml: (container, markup) => page.owners.pageDom.updateHtml(container, markup),
            bindEvent: (target, event, listener) => page.owners.pageResources.on(target, event, listener),
            filter: baseBindings.filterSettings,
            hasSearchQuery: baseBindings.hasSearchQuery
        }
    });
};

export { createConnectManager };
