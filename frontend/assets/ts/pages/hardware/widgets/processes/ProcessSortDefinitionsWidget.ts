/* SoAI - Hardware page process sort definitions widget [frontend/assets/ts/pages/hardware/widgets/processes/ProcessSortDefinitionsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ProcessSortColumn, SortDirection } from '@pages/hardware/widgets/processes/types.ts';

const PROCESS_SORT_COLUMNS: readonly ProcessSortColumn[] = ['name', 'pid', 'cpu', 'memory', 'runtime'];

const PROCESS_SORT_DEFAULT_DIRECTIONS: Readonly<Record<ProcessSortColumn, SortDirection>> = {
    name: 'asc',
    pid: 'desc',
    cpu: 'desc',
    memory: 'desc',
    runtime: 'desc'
};

export { PROCESS_SORT_COLUMNS, PROCESS_SORT_DEFAULT_DIRECTIONS };
