/* SoAI - Shared realtime task terminal handoff [frontend/assets/ts/core/realtime/streammanager/actions/taskTerminalHandoff.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import { secondsToMs } from '@core/time/durations.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const TASK_TERMINAL_HANDOFF_TTL_MS = secondsToMs(30);
const MAX_TASK_TERMINAL_HANDOFFS = 256;

const pruneTaskTerminalHandoffs = (state: StreamTaskRuntimeState, now: number): void => {
    for (const [taskId, handoff] of state.taskTerminalHandoffs) {
        if (handoff.expiresAt > now) continue;
        state.taskTerminalHandoffs.delete(taskId);
    }
    while (state.taskTerminalHandoffs.size >= MAX_TASK_TERMINAL_HANDOFFS) {
        const oldestTaskId = state.taskTerminalHandoffs.keys().next().value;
        if (typeof oldestTaskId !== 'string') return;
        state.taskTerminalHandoffs.delete(oldestTaskId);
    }
};

const retainTaskTerminalHandoff = (state: StreamTaskRuntimeState, taskId: string, payload: JsonObject): void => {
    const now = Date.now();
    pruneTaskTerminalHandoffs(state, now);
    state.taskTerminalHandoffs.delete(taskId);
    state.taskTerminalHandoffs.set(taskId, { payload, expiresAt: now + TASK_TERMINAL_HANDOFF_TTL_MS });
};

const consumeTaskTerminalHandoff = (state: StreamTaskRuntimeState, taskId: string): JsonObject | null => {
    const handoff = state.taskTerminalHandoffs.get(taskId);
    if (!handoff) return null;
    state.taskTerminalHandoffs.delete(taskId);
    return handoff.expiresAt > Date.now() ? handoff.payload : null;
};

export { consumeTaskTerminalHandoff, retainTaskTerminalHandoff };
