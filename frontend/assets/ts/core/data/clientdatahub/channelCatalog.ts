/* SoAI - Immutable V1 collection channel catalog [frontend/assets/ts/core/data/clientdatahub/channelCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionChannelDefinition, ResourceItem } from '@core/data/clientdatahub/types.ts';
import { MODELS, PLUGINS, PROMPTS } from '@core/realtime/streammanager/resources/ids.ts';

const textIdentity = (item: ResourceItem, fields: readonly string[]): string | null => {
    for (const field of fields) {
        const value = item[field];
        if (typeof value === 'string' && value.trim()) return value.trim();
        if (typeof value === 'number' && Number.isFinite(value)) return String(value);
    }
    return null;
};

const COLLECTION_CHANNEL_CATALOG: readonly CollectionChannelDefinition[] = Object.freeze([Object.freeze({ resource: MODELS, trackBy: (item: ResourceItem): string | null => textIdentity(item, ['universalId', 'id', 'name']) }), Object.freeze({ resource: PLUGINS, trackBy: (item: ResourceItem): string | null => textIdentity(item, ['name', 'id']) }), Object.freeze({ resource: PROMPTS, trackBy: (item: ResourceItem): string | null => textIdentity(item, ['id', 'name']) })]);

export { COLLECTION_CHANNEL_CATALOG };
