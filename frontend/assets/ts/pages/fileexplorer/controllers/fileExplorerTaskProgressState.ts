/* SoAI - File explorer page control layer task progress state [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerTaskProgressState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { FileExplorerTaskSnapshot } from '@pages/fileexplorer/controllers/fileExplorerTaskSummary.ts';

const pruneRecentTaskSnapshots = (recentUpdates: Map<string, FileExplorerTaskSnapshot>, cancelledTaskIds: Set<string>): void => {
    const now = Date.now();
    for (const [key, value] of recentUpdates.entries()) {
        if (now - value.at > 30_000) {
            recentUpdates.delete(key);
            cancelledTaskIds.delete(key);
        }
    }
    while (recentUpdates.size > 50) {
        const firstKey = recentUpdates.keys().next().value;
        if (typeof firstKey !== 'string') {
            break;
        }
        recentUpdates.delete(firstKey);
    }
};

export { pruneRecentTaskSnapshots };
