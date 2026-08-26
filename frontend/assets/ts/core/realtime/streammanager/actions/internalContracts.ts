/* SoAI - Shared realtime internal contracts [frontend/assets/ts/core/realtime/streammanager/actions/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OperationListener, OperationMetadata, StreamActionResult, TaskTerminalListener, TaskWatcher } from '@core/realtime/streammanager/types.ts';
import type { KeyedTaskAdmissionGate } from '@core/realtime/streammanager/actions/keyedTaskAdmission.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import type { TaskOperationEmitter } from '@core/realtime/streammanager/actions/acceptedTaskOperation.ts';
import type { StreamTaskDebugLogger, StreamTaskSafeInvoker } from '@core/realtime/streammanager/actions/types.ts';

interface StreamTaskExecutionRuntime {
    safe: StreamTaskSafeInvoker;
    state: StreamTaskRuntimeState;
    module: string;
    logWarn: StreamTaskDebugLogger;
    getTaskSnapshot: (taskId: string) => Promise<void>;
    emitOperation: TaskOperationEmitter;
    emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void;
    finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void;
    cancelTask?: (taskId: string, reason: string | null) => Promise<TaskCancellationResponse>;
}

interface StreamTaskRuntimeState {
    generation: number;
    operationListeners: Set<OperationListener>;
    operationHandlers: Map<string, StreamActionResult>;
    keyedTaskAdmissions: Map<string, KeyedTaskAdmissionGate>;
    trackedTasks: Map<string, OperationMetadata>;
    taskWatchers: Map<string, Set<TaskWatcher>>;
    taskRecoveryInFlight: Map<string, number>;
    taskSnapshotChecksInFlight: Map<string, number>;
    taskTerminalHandoffs: Map<string, { payload: JsonObject; expiresAt: number }>;
    taskReconnectInFlight: Promise<void> | null;
    terminalTaskListeners: Set<TaskTerminalListener>;
}

export type { StreamTaskExecutionRuntime, StreamTaskRuntimeState };
