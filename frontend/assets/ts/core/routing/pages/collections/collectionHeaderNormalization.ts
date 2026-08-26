/* SoAI - Shared routing collection header normalization [frontend/assets/ts/core/routing/pages/collections/collectionHeaderNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HeaderActionDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { HeaderConfig, HeaderMetadata } from '@core/routing/pages/collections/types.ts';

interface NormalizedHeaderResult {
    config: HeaderConfig;
    metadata: HeaderMetadata;
}

const normalizeCollectionHeader = (headerConfig: HeaderConfig | null | undefined): NormalizedHeaderResult => {
    const baseConfig: HeaderConfig = headerConfig ? { ...headerConfig } : {};
    const searchEnabled = baseConfig['searchEnabled'] !== false;
    if (baseConfig['searchEnabled'] !== undefined) {
        delete baseConfig['searchEnabled'];
    }
    const actions: HeaderActionDefinition[] = baseConfig.actions ? [...baseConfig.actions] : [];
    const hasSearchAction = actions.some((action) => action.type === 'search');
    if (searchEnabled && !hasSearchAction) {
        actions.unshift({ type: 'search' });
    }
    baseConfig.actions = actions;
    return {
        config: baseConfig,
        metadata: { searchEnabled }
    };
};

export { normalizeCollectionHeader };
export type { NormalizedHeaderResult };
