/* SoAI - Attachment browser presentation records [frontend/assets/ts/features/attachmodal/browseRecords.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { SortState } from '@core/ui/tables/sortableTable.ts';

type AttachBrowseSortColumn = 'name' | 'type' | 'size' | 'modified';
type AttachBrowseSortState = SortState<AttachBrowseSortColumn>;
interface AttachBrowseResult {
    key: string;
    title: string;
    status: string;
    iconName: IconName;
    typeLabel: string;
    sizeLabel: string;
    modifiedLabel: string;
    sortSize: number;
    sortModified: number;
}

export type { AttachBrowseResult, AttachBrowseSortColumn, AttachBrowseSortState };
