/* SoAI - Catalog feature service [frontend/assets/ts/features/catalog/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { CatalogStore } from '@features/catalog/catalogSubscriptionManager.ts';

const CATALOG_STORE_SERVICE_ID = 'features.catalog.store';

const isCatalogStore = <T>(value: T): value is T & CatalogStore => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'subscribe') && hasFunctionProperty(value, 'ensureLoaded') && hasFunctionProperty(value, 'refresh') && hasFunctionProperty(value, 'getPlugins') && hasFunctionProperty(value, 'getCapabilityManifest') && hasFunctionProperty(value, 'ensureCapabilityManifestReady');
};

const requireCatalogStore = (): CatalogStore => {
    const candidate = resolveKernelService(CATALOG_STORE_SERVICE_ID);
    if (!isCatalogStore(candidate)) {
        throw new Error(`${CATALOG_STORE_SERVICE_ID} must expose the catalog store contract`);
    }
    return candidate;
};

export { CATALOG_STORE_SERVICE_ID, isCatalogStore, requireCatalogStore };
