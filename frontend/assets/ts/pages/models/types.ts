/* SoAI - Models page public contracts [frontend/assets/ts/pages/models/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionLayout } from '@core/collectionpage/publicContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { BuildConfig } from '@core/uiprimitives/types.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';

interface ModelsUiRefs {
    root: HTMLElement;
    downloadProgress: HTMLElement;
    grid: HTMLElement;
    listBody: HTMLElement;
    viewModeToggleButton: HTMLButtonElement;
}

type GetIconSyncFunctionValue = (iconName: IconName, options?: IconOptions) => TrustedHtml;
type BuildLayoutFunctionValue = (config: BuildConfig) => CollectionLayout;

interface ModelsLayoutBuildDependencies {
    getIconSync: GetIconSyncFunctionValue;
    buildLayout: BuildLayoutFunctionValue;
    sortBy: string;
    sortOrder: SortDirection;
    onSortChange: (event: Event) => void;
}

interface ModelsLayoutViewHost {
    getIconSync: GetIconSyncFunctionValue;
    sortBy: string;
    sortOrder: SortDirection;
}

interface ModelsPageDependencies {
    catalogStore: CatalogStore;
}

export type { BuildLayoutFunctionValue, GetIconSyncFunctionValue, ModelsLayoutBuildDependencies, ModelsLayoutViewHost, ModelsPageDependencies, ModelsUiRefs };
