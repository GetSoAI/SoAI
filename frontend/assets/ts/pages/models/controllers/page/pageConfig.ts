/* SoAI - Models page configuration [frontend/assets/ts/pages/models/controllers/page/pageConfig.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { stableModelFingerprint } from '@core/models/modelFingerprint.ts';
import { normalizeModelRecord } from '@core/models/modelRecordNormalization.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { MODELS } from '@core/realtime/streammanager/resources/ids.ts';
import { modelsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';
import { normalizeResourceItem } from '@core/data/clientdatahub/guards.ts';
import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import type { StoreItemRecord } from '@core/CollectionsStore.ts';

const createModelsPageCollectionConfig = (): { checkerboardSelector: string; collectionKey: string; collectionOptions: { normalizeId: (model: StoreItemRecord) => string | null; normalize: (model: ResourceIncomingValue) => ResourceItem; fingerprint: (model: ResourceItem) => string }; defaultSort: string; searchPlaceholder: string } => ({
    checkerboardSelector: modelsPageConfig.grid.cardSelector,
    collectionKey: MODELS,
    collectionOptions: {
        normalizeId: (model: StoreItemRecord): string | null => {
            if (!isObject(model)) return null;
            const universalId = model['universalId'];
            if (isString(universalId) && universalId) return universalId;
            const id = model['id'];
            if (isString(id) && id) return id;
            const name = model['name'];
            if (isString(name) && name) return name;
            return null;
        },
        normalize: (model: ResourceIncomingValue): ResourceItem => {
            const normalized = isJsonValue(model) ? normalizeModelRecord(model) : null;
            return normalizeResourceItem(normalized ?? model, 'ModelsPage collection item');
        },
        fingerprint: (model: ResourceItem): string => stableModelFingerprint(toJsonCompatibleValue(model))
    },
    defaultSort: 'name',
    searchPlaceholder: i18n.t('models.searchPlaceholder')
});

export { createModelsPageCollectionConfig };
