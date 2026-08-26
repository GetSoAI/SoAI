/* SoAI - Plugin page persistence contract [frontend/assets/ts/features/plugins/contracts/pluginPageStorage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PluginsPageControlState } from '@core/storage/types.ts';

interface PluginsFiltersStorage {
    getPageControlState(pageId: 'plugins'): PluginsPageControlState;
    setPageControlState(pageId: 'plugins', filters: Partial<PluginsPageControlState>): void;
}

export type { PluginsFiltersStorage };
