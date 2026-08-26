/* SoAI - Tasks feature terminal events [frontend/assets/ts/features/tasks/taskmanagerstore/terminalEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TaskTerminalEvent } from '@core/realtime/streammanager/types.ts';
import type { TaskManagerStoreState } from '@features/tasks/taskmanagerstore/state.ts';

interface TerminalTaskEventContext {
    state: TaskManagerStoreState;
    notify: () => void;
}

const MAX_RETAINED_TERMINAL_TASK_IDS = 500;

const rememberTerminalTaskId = (state: TaskManagerStoreState, taskId: string): void => {
    state.terminalTaskIds.add(taskId);
    while (state.terminalTaskIds.size > MAX_RETAINED_TERMINAL_TASK_IDS) {
        const firstTerminalTaskId = state.terminalTaskIds.values().next().value;
        if (!firstTerminalTaskId) {
            break;
        }
        state.terminalTaskIds.delete(firstTerminalTaskId);
    }
};

const handleTerminalTaskEvent = (context: TerminalTaskEventContext, event: TaskTerminalEvent | null | undefined): void => {
    const taskId = typeof event?.taskId === 'string' ? event.taskId.trim() : '';
    if (!taskId) {
        return;
    }
    rememberTerminalTaskId(context.state, taskId);
    if (context.state.operations.delete(taskId)) {
        context.notify();
    }
};

export { handleTerminalTaskEvent };
