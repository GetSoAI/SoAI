/* SoAI - Search feature type metadata [frontend/assets/ts/features/search/searchTypeMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeSearchCategory } from '@core/search/searchCategory.ts';
import type { TypeMetadata } from '@core/search/searchTypes.ts';

const DEFAULT_TYPE_METADATA_MAP: Readonly<Record<string, TypeMetadata>> = Object.freeze({
    model: { icon: 'model-default' },
    virtual: { icon: 'model-default' },
    plugin: { icon: 'plugin' },
    device: { icon: 'hardware' },
    hardware: { icon: 'hardware' },
    config: { icon: 'settings' },
    configuration: { icon: 'settings' },
    page: { icon: 'file-generic' },
    files: { icon: 'file-generic' },
    conversation: { icon: 'chat' },
    prompt: { icon: 'prompt' },
    help: { icon: 'help' },
    modal: { icon: 'settings' },
    'power-actions': { icon: 'power' }
});

const getTypeMetadata = (category: string, map: Record<string, TypeMetadata> = DEFAULT_TYPE_METADATA_MAP): TypeMetadata => {
    const normalizedCategory = normalizeSearchCategory(category);
    if (!normalizedCategory) {
        throw new Error('Search type metadata category must be non-empty');
    }
    const metadata = map[normalizedCategory];
    if (!metadata) {
        throw new Error(`Unsupported search type metadata category "${normalizedCategory}"`);
    }
    return metadata;
};

export { DEFAULT_TYPE_METADATA_MAP, getTypeMetadata };
