/* SoAI - Settings initial modal query handling [frontend/assets/ts/pages/settings/controllers/page/initialModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { consumeRouteQuery, INITIAL_MODAL_QUERY_KEYS } from '@core/routeregistry/reconstruction.ts';
import type { PageRouting } from '@core/routing/router/types.ts';

interface SettingsInitialModalHost {
    router: Pick<PageRouting, 'getRouteParameters' | 'getCurrentRoute' | 'getQueryParameters' | 'replaceCurrentRoute'> | null;
}

interface SettingsInitialMcpManager {
    openCreateServerModal(): Promise<void>;
}

const clearSettingsInitialModalQuery = (host: SettingsInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Settings initial modal cleanup requires a router');
    }
    consumeRouteQuery(router, INITIAL_MODAL_QUERY_KEYS);
};

const handleSettingsInitialModal = async (host: SettingsInitialModalHost, mcpManager: SettingsInitialMcpManager | null): Promise<void> => {
    const router = host.router;
    if (!router) {
        throw new Error('Settings initial modal requires a router');
    }
    if (router.getRouteParameters()['modal'] !== 'add-mcp-server') {
        return;
    }
    if (!mcpManager) {
        throw new Error('Settings MCP server modal requires the MCP manager');
    }
    await mcpManager.openCreateServerModal();
    clearSettingsInitialModalQuery(host);
};

export { handleSettingsInitialModal };
