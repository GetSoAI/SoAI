/* SoAI - Models page control layer rendering [frontend/assets/ts/pages/models/controllers/page/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionLayout } from '@core/collectionpage/publicContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { BuildConfig } from '@core/uiprimitives/types.ts';
import { buildModelsLayout } from '@pages/models/view.ts';

interface ModelsLayoutDependencies {
    sortBy: string;
    sortOrder: 'asc' | 'desc';
    onSortChange: (event: Event) => void;
    buildLayout: (config: BuildConfig) => CollectionLayout;
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
}

interface ModelsPageLayoutHost {
    sortBy: string;
    sortOrder: 'asc' | 'desc';
    onSortChange: (event: Event) => void;
    createLayoutBuilder: () => {
        build(config: BuildConfig): CollectionLayout;
    };
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
}

const buildModelsCollectionLayout = (dependencies: ModelsLayoutDependencies): CollectionLayout => {
    return buildModelsLayout({
        getIconSync: (iconName: IconName, options?: IconOptions) => dependencies.getIconSync(iconName, options),
        buildLayout: (config) => dependencies.buildLayout(config),
        sortBy: dependencies.sortBy,
        sortOrder: dependencies.sortOrder,
        onSortChange: dependencies.onSortChange
    });
};

const createModelsPageCollectionLayout = (host: ModelsPageLayoutHost): CollectionLayout => {
    const builder = host.createLayoutBuilder();
    return buildModelsCollectionLayout({
        sortBy: host.sortBy,
        sortOrder: host.sortOrder,
        onSortChange: host.onSortChange,
        buildLayout: (config) => builder.build(config),
        getIconSync: (iconName, options) => host.getIconSync(iconName, options)
    });
};

export { buildModelsCollectionLayout, createModelsPageCollectionLayout };
export type { ModelsPageLayoutHost };
