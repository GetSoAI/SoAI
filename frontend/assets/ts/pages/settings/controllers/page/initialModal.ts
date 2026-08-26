/* SoAI - Settings initial modal query handling [frontend/assets/ts/pages/settings/controllers/page/initialModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildRouteWithoutQueryParameters } from '@core/routing/router/events.ts';

interface SettingsInitialModalHost {
    router: {
        getRouteParameters(): Record<string, string>;
        replaceCurrentRoute(target: string): void;
    } | null;
}

interface SettingsInitialMcpManager {
    openCreateServerModal(): Promise<void>;
}

const clearSettingsInitialModalQuery = (host: SettingsInitialModalHost): void => {
    const router = host.router;
    if (!router) {
        throw new Error('Settings initial modal cleanup requires a router');
    }
    router.replaceCurrentRoute(buildRouteWithoutQueryParameters('settings', router.getRouteParameters(), ['modal']));
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
