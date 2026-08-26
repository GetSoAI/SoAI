/* SoAI - Shared realtime actions effects [frontend/assets/ts/core/realtime/streammanager/actions/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildTerminalTaskPayload, finalizeTrackedTask } from '@core/realtime/streammanager/actions/completion.ts';
import { buildDetachedTaskPayload } from '@core/realtime/streammanager/actions/detachedTaskPayload.ts';
import { buildTrackedTaskOperation } from '@core/realtime/streammanager/actions/taskOperations.ts';
import { normalizeWebSocketPayload } from '@core/realtime/streammanager/transport/normalizeWebSocketPayload.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';
import type { StreamTaskDebugLogger, StreamTaskWebSocketProvider } from '@core/realtime/streammanager/actions/types.ts';
import { type JsonObject, isJsonArray } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import { resolveTaskSnapshotRetryDelayMs, shouldReportTaskSnapshotFailure, TASK_SNAPSHOT_POLL_INTERVAL_MS } from '@core/realtime/streammanager/actions/taskSupervisionPolicy.ts';

interface TaskCompletionPayloadOptions {
    taskId: string;
    emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => void;
    finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void;
    emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void;
}

interface TaskRecoveryOptions {
    taskId: string;
    payload: JsonObject;
    module: string;
    state: StreamTaskRuntimeState;
    getWebSocket: StreamTaskWebSocketProvider;
    emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => void;
    emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void;
    finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void;
    logDebug: StreamTaskDebugLogger;
}

interface TaskRestoreOptions {
    state: StreamTaskRuntimeState;
    getWebSocket: StreamTaskWebSocketProvider;
    emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => void;
    emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void;
    finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void;
}

interface MissingTaskSettlementOptions {
    state: StreamTaskRuntimeState;
    emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => void;
    finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void;
}

const hasTaskSupervisionDemand = (state: StreamTaskRuntimeState, taskId: string): boolean => {
    if (state.taskWatchers.has(taskId)) return true;
    const metadata = state.trackedTasks.get(taskId);
    const operationKey = toTrimmedString(metadata?.['operationKey']);
    const requestId = toTrimmedString(metadata?.['requestId']);
    return Boolean(operationKey && requestId === taskId && state.keyedTaskAdmissions.get(operationKey)?.requestId === taskId);
};

const settleMissingTask = (options: MissingTaskSettlementOptions, taskId: string): void => {
    const metadata = options.state.trackedTasks.get(taskId) ?? null;
    const hasWatchers = options.state.taskWatchers.has(taskId);
    options.state.trackedTasks.delete(taskId);
    if (metadata) {
        if (metadata.type !== 'unknown') {
            options.emitOperation(taskId, metadata.type, 'detached', { ...metadata, taskStatus: 'detached' }, {});
        }
    }
    if (hasWatchers) {
        options.finalizeTaskWatchers(taskId, buildDetachedTaskPayload(taskId));
    }
};

const settleTaskFromSnapshot = (options: { taskId: string; state: StreamTaskRuntimeState } & TaskCompletionPayloadOptions, snapshot: JsonObject | null): boolean => {
    if (!snapshot) throw new Error(`Task snapshot is unavailable for ${options.taskId}`);
    const snapshotTaskId = toTrimmedString(snapshot['task_id']);
    if (snapshotTaskId !== options.taskId) throw new Error(`Task snapshot identity mismatch for ${options.taskId}`);
    const status = toTrimmedString(snapshot['status']);
    if (!status) throw new Error(`Task snapshot status is missing for ${options.taskId}`);
    const payload = buildTerminalTaskPayload(options.taskId, snapshot);
    if (!payload) return false;
    finalizeTrackedTask({
        taskId: options.taskId,
        payload,
        trackedTasks: options.state.trackedTasks,
        hasTaskWatchers: (taskId: string) => options.state.taskWatchers.has(taskId),
        emitOperation: options.emitOperation,
        emitTerminalTask: options.emitTerminalTask,
        finalizeTaskWatchers: options.finalizeTaskWatchers
    });
    return true;
};

const recoverTaskFromSnapshot = async (options: TaskRecoveryOptions): Promise<void> => {
    const normalizedTaskId = toTrimmedString(options.taskId);
    if (!normalizedTaskId) return;
    const recoveryGeneration = options.state.generation;
    if (options.state.trackedTasks.has(normalizedTaskId) || options.state.taskRecoveryInFlight.has(normalizedTaskId)) {
        return;
    }

    options.state.taskRecoveryInFlight.set(normalizedTaskId, recoveryGeneration);
    try {
        const ws = options.getWebSocket();
        if (!ws) return;
        const snapshot = await ws.requestSnapshot('tasks.by_id', { 'task_id': normalizedTaskId });
        if (options.state.generation !== recoveryGeneration) return;
        const normalizedSnapshot = normalizeWebSocketPayload(snapshot?.data);
        if (!normalizedSnapshot) return;
        const operation = buildTrackedTaskOperation(normalizedSnapshot);
        if (!operation) return;
        if (operation.id !== normalizedTaskId) throw new Error(`Recovered task snapshot identity mismatch for ${normalizedTaskId}`);

        const existing = options.state.trackedTasks.get(operation.id);
        const mergedMeta = existing ? { ...existing, ...operation.meta, type: operation.type, id: operation.id } : operation.meta;
        const status = toTrimmedString(normalizedSnapshot['status']);
        if (!status) throw new Error(`Recovered task snapshot status is missing for ${normalizedTaskId}`);
        const terminalPayload = buildTerminalTaskPayload(operation.id, normalizedSnapshot);
        if (terminalPayload) {
            options.state.trackedTasks.set(operation.id, mergedMeta);
            finalizeTrackedTask({
                taskId: operation.id,
                payload: terminalPayload,
                trackedTasks: options.state.trackedTasks,
                hasTaskWatchers: (taskId: string) => options.state.taskWatchers.has(taskId),
                emitOperation: options.emitOperation,
                emitTerminalTask: options.emitTerminalTask,
                finalizeTaskWatchers: options.finalizeTaskWatchers,
                meta: mergedMeta
            });
            return;
        }
        options.state.trackedTasks.set(operation.id, mergedMeta);

        if (!existing && operation.type !== 'unknown') {
            options.emitOperation(operation.id, operation.type, 'start', mergedMeta, operation.progress !== null ? { progress: operation.progress } : {});
        }
        if (operation.type !== 'unknown') {
            options.emitOperation(operation.id, operation.type, 'progress', mergedMeta, { ...normalizedSnapshot, ...options.payload });
        }
    } catch (error) {
        const normalizedError = ensureError(error);
        options.logDebug(options.module, 'Task recovery from progress snapshot failed', normalizedError);
    } finally {
        if (options.state.taskRecoveryInFlight.get(normalizedTaskId) === recoveryGeneration) {
            options.state.taskRecoveryInFlight.delete(normalizedTaskId);
        }
    }
};

const checkTaskSnapshot = async (
    options: {
        module: string;
        taskId: string;
        state: StreamTaskRuntimeState;
        getWebSocket: StreamTaskWebSocketProvider;
        logDebug: StreamTaskDebugLogger;
    } & TaskCompletionPayloadOptions
): Promise<void> => {
    const snapshotCheckGeneration = options.state.generation;
    if (options.state.taskSnapshotChecksInFlight.has(options.taskId)) {
        return;
    }
    options.state.taskSnapshotChecksInFlight.set(options.taskId, snapshotCheckGeneration);
    performance.mark(`soai-audit:snapshot-start:${options.taskId}`);
    let consecutiveFailureCount = 0;
    try {
        while (options.state.generation === snapshotCheckGeneration && hasTaskSupervisionDemand(options.state, options.taskId)) {
            let nextCheckDelayMs = TASK_SNAPSHOT_POLL_INTERVAL_MS;
            try {
                const currentWebSocket = options.getWebSocket();
                if (!currentWebSocket) {
                    throw new Error('Task snapshot transport is unavailable');
                }
                const snapshot = await currentWebSocket.requestSnapshot('tasks.by_id', { 'task_id': options.taskId });
                if (options.state.generation !== snapshotCheckGeneration) return;
                if (!snapshot) throw new Error(`Task snapshot response is unavailable for ${options.taskId}`);
                if (snapshot.data === null) {
                    settleMissingTask(options, options.taskId);
                    return;
                }
                if (settleTaskFromSnapshot(options, normalizeWebSocketPayload(snapshot.data))) return;
                consecutiveFailureCount = 0;
            } catch (error) {
                if (options.state.generation !== snapshotCheckGeneration) return;
                consecutiveFailureCount += 1;
                nextCheckDelayMs = resolveTaskSnapshotRetryDelayMs(consecutiveFailureCount);
                if (shouldReportTaskSnapshotFailure(consecutiveFailureCount)) {
                    options.logDebug(options.module, `Task snapshot check failed; retry ${consecutiveFailureCount}`, ensureError(error));
                }
            }
            if (options.state.generation === snapshotCheckGeneration && hasTaskSupervisionDemand(options.state, options.taskId)) {
                await sleepMs(nextCheckDelayMs);
            }
        }
    } finally {
        performance.mark(`soai-audit:snapshot-end:${options.taskId}`);
        if (options.state.taskSnapshotChecksInFlight.get(options.taskId) === snapshotCheckGeneration) {
            options.state.taskSnapshotChecksInFlight.delete(options.taskId);
        }
    }
};

const reconcileOperationsFromSnapshots = async (options: TaskRestoreOptions): Promise<void> => {
    const reconciliationGeneration = options.state.generation;
    const ws = options.getWebSocket();
    if (!ws) return;
    const snapshot = await ws.requestSnapshot('tasks.active');
    if (options.state.generation !== reconciliationGeneration) return;
    const normalized = normalizeWebSocketPayload(snapshot?.data);
    if (!normalized || !isJsonArray(normalized['tasks'])) throw new Error('Active task snapshot must include a tasks array');

    const active = new Map<string, { type: string; meta: OperationMetadata; progress: number | null }>();
    for (const task of normalized['tasks']) {
        const operation = buildTrackedTaskOperation(task);
        if (!operation) throw new Error('Active task snapshot contains a malformed task');
        if (active.has(operation.id)) throw new Error(`Active task snapshot contains duplicate task ${operation.id}`);
        active.set(operation.id, { type: operation.type, meta: operation.meta, progress: operation.progress });
    }

    for (const [taskId, operation] of active.entries()) {
        const existing = options.state.trackedTasks.get(taskId);
        const mergedMeta = existing ? { ...existing, ...operation.meta, type: operation.type, id: taskId } : operation.meta;
        options.state.trackedTasks.set(taskId, mergedMeta);
        if (operation.type === 'unknown') continue;
        if (!existing) {
            options.emitOperation(taskId, operation.type, 'start', mergedMeta, operation.progress !== null ? { progress: operation.progress } : {});
        } else if (operation.progress !== null) {
            options.emitOperation(taskId, operation.type, 'progress', mergedMeta, { progress: operation.progress });
        }
    }

    const endedTaskIds = Array.from(options.state.trackedTasks.keys()).filter((taskId) => !active.has(taskId));
    const snapshotResults = await Promise.all(
        endedTaskIds.map(async (taskId) => {
            const snapshotResponse = await ws.requestSnapshot('tasks.by_id', { 'task_id': taskId });
            if (!snapshotResponse) throw new Error(`Task snapshot response is unavailable for ${taskId}`);
            if (snapshotResponse.data === null) return { taskId, payload: null, isMissing: true };
            const taskSnapshot = normalizeWebSocketPayload(snapshotResponse.data);
            if (!taskSnapshot) throw new Error(`Task snapshot is unavailable for ${taskId}`);
            if (toTrimmedString(taskSnapshot['task_id']) !== taskId) throw new Error(`Task snapshot identity mismatch for ${taskId}`);
            const status = toTrimmedString(taskSnapshot['status']);
            if (!status) throw new Error(`Task snapshot status is missing for ${taskId}`);
            const payload = buildTerminalTaskPayload(taskId, taskSnapshot);
            return { taskId, payload, isMissing: false };
        })
    );
    if (options.state.generation !== reconciliationGeneration) return;

    for (const result of snapshotResults) {
        if (result.isMissing) {
            settleMissingTask(options, result.taskId);
            continue;
        }
        if (!result.payload) continue;
        const meta = options.state.trackedTasks.get(result.taskId);
        if (!meta) continue;
        finalizeTrackedTask({
            taskId: result.taskId,
            payload: result.payload,
            trackedTasks: options.state.trackedTasks,
            hasTaskWatchers: (taskId: string) => options.state.taskWatchers.has(taskId),
            emitOperation: options.emitOperation,
            emitTerminalTask: options.emitTerminalTask,
            finalizeTaskWatchers: options.finalizeTaskWatchers,
            meta
        });
    }
};

const reconnectOperations = async (options: TaskRestoreOptions): Promise<void> => {
    const activeReconciliation = options.state.taskReconnectInFlight;
    if (activeReconciliation) return await activeReconciliation;
    const reconciliation = reconcileOperationsFromSnapshots(options);
    options.state.taskReconnectInFlight = reconciliation;
    try {
        await reconciliation;
    } finally {
        if (options.state.taskReconnectInFlight === reconciliation) {
            options.state.taskReconnectInFlight = null;
        }
    }
};

export { checkTaskSnapshot, recoverTaskFromSnapshot, reconnectOperations };
