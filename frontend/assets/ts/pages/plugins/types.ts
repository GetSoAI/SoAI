/* SoAI - Plugins page contracts [frontend/assets/ts/pages/plugins/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CatalogStore } from '@features/catalog/public.ts';
import type { FirstRunModalService } from '@core/firstrun/protocols.ts';
import type { PluginsFiltersStorage } from '@features/plugins/public.ts';

interface RestartOverlayService {
    show(value: string): void;
}

interface PluginsPageDependencies {
    catalogStore: CatalogStore;
    storage: PluginsFiltersStorage;
    restartOverlay: RestartOverlayService;
    firstRunModals: FirstRunModalService;
}

export type { PluginsPageDependencies, RestartOverlayService };
