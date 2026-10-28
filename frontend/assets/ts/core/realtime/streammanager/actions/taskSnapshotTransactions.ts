/* SoAI - Task snapshot and live-event precedence [frontend/assets/ts/core/realtime/streammanager/actions/taskSnapshotTransactions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';

const beginTaskSnapshot = (state: StreamTaskRuntimeState): Set<string> => {
    const changedTasks = new Set<string>();
    state.pendingTaskSnapshots.add(changedTasks);
    return changedTasks;
};

const recordTaskLiveChange = (state: StreamTaskRuntimeState, taskId: string): void => {
    for (const snapshot of state.pendingTaskSnapshots) snapshot.add(taskId);
};

const recordTaskTerminal = (state: StreamTaskRuntimeState, taskId: string): void => {
    recordTaskLiveChange(state, taskId);
    state.terminalTaskIds.add(taskId);
    while (state.terminalTaskIds.size > 500) {
        const oldest = state.terminalTaskIds.values().next().value;
        if (typeof oldest !== 'string') break;
        state.terminalTaskIds.delete(oldest);
    }
};

export { beginTaskSnapshot, recordTaskLiveChange, recordTaskTerminal };
