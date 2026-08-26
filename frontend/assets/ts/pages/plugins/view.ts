/* SoAI - Plugins page rendering [frontend/assets/ts/pages/plugins/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionLayout } from '@core/collectionpage/publicContracts.ts';
import type { PluginLayoutBuildDependencies } from '@pages/plugins/rendering/contracts.ts';
import { buildPluginsHeader, buildPluginsSections } from '@pages/plugins/rendering/mappers.ts';

const buildPluginsLayout = ({ getIconSync, buildLayout, sortBy, sortOrder, onSortChange }: PluginLayoutBuildDependencies): CollectionLayout => {
    return buildLayout({
        header: buildPluginsHeader(getIconSync, sortBy, sortOrder),
        sections: buildPluginsSections(sortBy, sortOrder),
        filters: {
            '#provider-filter': 'filterProvider',
            '#status-filter': 'filterStatus'
        },
        actions: [{ selector: '#plugins-sort', event: 'change', handler: onSortChange }],
        delegated: []
    });
};

export { buildPluginsLayout };
