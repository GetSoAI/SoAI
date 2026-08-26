/* SoAI - Shared layout task busy rules [frontend/assets/ts/core/layout/sidebar/taskBusyRules.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SidebarBusyPageId } from '@core/layout/sidebar/busyIndicatorRegistry.ts';
import { isTerminalOperationStatus } from '@core/tasks/operationPayloads.ts';

type SidebarTaskBusyPageId = Extract<SidebarBusyPageId, 'plugins' | 'models' | 'fileExplorer'>;

const SIDEBAR_TASK_BUSY_PAGE_IDS: readonly SidebarTaskBusyPageId[] = Object.freeze(['plugins', 'models', 'fileExplorer']);

const SIDEBAR_TASK_BUSY_OPERATION_TYPES: Readonly<Record<SidebarTaskBusyPageId, readonly string[]>> = Object.freeze({
    plugins: Object.freeze(['backend-install', 'backend-update', 'backend-update-all', 'plugin-clone']),
    models: Object.freeze(['model-download']),
    fileExplorer: Object.freeze(['file-explorer-op'])
});

const resolveSidebarTaskBusyPageId = (operationType: string): SidebarTaskBusyPageId | null => {
    for (const pageId of SIDEBAR_TASK_BUSY_PAGE_IDS) {
        if (SIDEBAR_TASK_BUSY_OPERATION_TYPES[pageId].includes(operationType)) {
            return pageId;
        }
    }
    return null;
};

export { SIDEBAR_TASK_BUSY_PAGE_IDS, isTerminalOperationStatus, resolveSidebarTaskBusyPageId };
export type { SidebarTaskBusyPageId };
