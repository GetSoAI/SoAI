/* SoAI - Plugins page rendering contracts [frontend/assets/ts/pages/plugins/rendering/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionLayout } from '@core/collectionpage/publicContracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { BuildConfig } from '@core/uiprimitives/types.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';
import type { CollectionDisplayMode } from '@core/uiprimitives/viewmode/collection.ts';

type GetIconSyncFunctionValue = (iconName: IconName, options?: IconOptions) => TrustedHtml;
type BuildLayoutFunctionValue = (config: BuildConfig) => CollectionLayout;

interface PluginLayoutBuildDependencies {
    viewMode: CollectionDisplayMode;
    getIconSync: GetIconSyncFunctionValue;
    buildLayout: BuildLayoutFunctionValue;
    sortBy: string;
    sortOrder: SortDirection;
    onSortChange: (event: Event) => void;
}

export type { BuildLayoutFunctionValue, GetIconSyncFunctionValue, PluginLayoutBuildDependencies };
