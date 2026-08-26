/* SoAI - Models page rendering [frontend/assets/ts/pages/models/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionLayout } from '@core/collectionpage/publicContracts.ts';
import { buildModelsLayoutDom } from '@pages/models/dom.ts';
import type { BuildLayoutFunctionValue, ModelsLayoutBuildDependencies } from '@pages/models/types.ts';

const buildModelsLayout = ({ getIconSync, buildLayout, sortBy, sortOrder, onSortChange }: ModelsLayoutBuildDependencies): CollectionLayout => {
    const viewHost = {
        getIconSync,
        sortBy,
        sortOrder
    };
    const layout = buildModelsLayoutDom(viewHost);
    return buildLayout({
        header: layout.header,
        sections: layout.sections,
        filters: layout.filters,
        actions: [{ selector: '#models-sort', event: 'change', handler: onSortChange }],
        delegated: []
    });
};

export { buildModelsLayout };
export type { BuildLayoutFunctionValue };
