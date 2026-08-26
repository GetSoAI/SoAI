/* SoAI - File explorer page control layer task summary [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerTaskSummary.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampPercent } from '@core/primitives/clampNumber.ts';

interface FileExplorerTaskSnapshot {
    progress: number;
    message: string;
    details: string;
    state: 'info' | 'success' | 'error';
    at: number;
}

interface FileExplorerTaskSummary {
    progress: number;
    latestTaskId: string;
    latestTaskLabel: string;
}

const resolveFileExplorerTaskSummary = (trackedTaskIds: ReadonlySet<string>, recentUpdates: ReadonlyMap<string, FileExplorerTaskSnapshot>): FileExplorerTaskSummary => {
    const activeTaskIds = Array.from(trackedTaskIds);
    if (activeTaskIds.length > 0) {
        let totalProgress = 0;
        let latestTaskId = '-';
        let latestTaskLabel = '';
        let latestAt = -1;
        for (const taskId of activeTaskIds) {
            const snapshot = recentUpdates.get(taskId);
            totalProgress += clampPercent(snapshot?.progress ?? 0);
            const snapshotAt = snapshot?.at ?? 0;
            if (snapshotAt >= latestAt) {
                latestAt = snapshotAt;
                latestTaskId = taskId;
                latestTaskLabel = snapshot?.message ?? '';
            }
        }
        return {
            progress: Math.round(totalProgress / activeTaskIds.length),
            latestTaskId,
            latestTaskLabel
        };
    }
    let latestTaskId = '-';
    let latestTaskLabel = '';
    let progress = 0;
    let latestAt = -1;
    for (const [taskId, snapshot] of recentUpdates.entries()) {
        if (snapshot.at < latestAt) {
            continue;
        }
        latestAt = snapshot.at;
        latestTaskId = taskId;
        latestTaskLabel = snapshot.message;
        progress = snapshot.state === 'success' ? 100 : clampPercent(snapshot.progress);
    }
    return { progress, latestTaskId, latestTaskLabel };
};

export { resolveFileExplorerTaskSummary };
export type { FileExplorerTaskSnapshot };
