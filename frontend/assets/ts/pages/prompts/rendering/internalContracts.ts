/* SoAI - Prompts page internal contracts [frontend/assets/ts/pages/prompts/rendering/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';
import type { CollectionDisplayMode } from '@core/uiprimitives/viewmode/collection.ts';

type PromptsGetIconSync = (iconName: IconName, options?: IconOptions) => TrustedHtml;

interface PromptsLayoutBuildDependencies {
    viewMode: CollectionDisplayMode;
    getIconSync: PromptsGetIconSync;
    sortBy: string;
    sortOrder: SortDirection;
    onSortChange: (event: Event) => void;
}

export type { PromptsGetIconSync, PromptsLayoutBuildDependencies };
