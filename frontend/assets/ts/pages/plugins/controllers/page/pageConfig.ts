/* SoAI - Plugins page configuration [frontend/assets/ts/pages/plugins/controllers/page/pageConfig.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { StoreItemRecord } from '@core/CollectionsStore.ts';
import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import { PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { isObject } from '@core/typeGuards.ts';
import { stablePluginFingerprint } from '@features/catalog/public.ts';
import { PLUGIN_CARD_SELECTOR } from '@pages/plugins/controllers/pluginsPageRuntimeSupport.ts';

const normalizePluginCollectionId = (candidate: StoreItemRecord): string | null => {
    if (!isObject(candidate)) return null;
    const name = toTrimmedString(candidate['name']);
    const id = toTrimmedString(candidate['id']);
    return name || id || null;
};

const createPluginsCollectionPageConfig = (): { checkerboardSelector: string; collectionKey: string; collectionOptions: { normalizeId: (candidate: StoreItemRecord) => string | null; fingerprint: (plugin: ResourceItem, raw?: ResourceIncomingValue) => string }; defaultSort: string; searchPlaceholder: string } => ({
    checkerboardSelector: PLUGIN_CARD_SELECTOR,
    collectionKey: PLUGINS,
    collectionOptions: {
        normalizeId: normalizePluginCollectionId,
        fingerprint: (plugin: ResourceItem, raw?: ResourceIncomingValue): string => stablePluginFingerprint(toJsonCompatibleValue(raw ?? plugin))
    },
    defaultSort: 'none',
    searchPlaceholder: i18n.t('plugins.searchPlaceholder')
});

export { createPluginsCollectionPageConfig };
