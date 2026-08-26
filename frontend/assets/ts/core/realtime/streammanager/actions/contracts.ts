/* SoAI - Shared frontend realtime stream manager actions boundary contracts [frontend/assets/ts/core/realtime/streammanager/actions/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OperationListener, OperationEvent, StreamActionResult, TaskTerminalListener } from '@core/realtime/streammanager/types.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';

interface StreamTaskRuntimeContract {
    handleTaskWebSocketEvent(eventType: string, payload: JsonObject): void;
    reset(): void;
    subscribeOperations(listener: OperationListener): () => void;
    subscribeTerminalTasks(listener: TaskTerminalListener): () => void;
    notifyOperationListeners(event: OperationEvent): void;
    taskAction(
        endpoint: string,
        options?: {
            method?: string;
            body?: ApiRequestBody;
            headers?: Record<string, string>;
            handlers?: StreamActionHandlers;
            operation?: JsonObject | null;
            allowDiscovery?: boolean;
            timeoutMs?: number;
        }
    ): StreamActionResult;
    taskCommand(
        command: JsonObject,
        options?: {
            handlers?: StreamActionHandlers;
            operation?: JsonObject | null;
            timeoutMs?: number;
        }
    ): StreamActionResult;
    trackAcceptedTask(
        taskId: string,
        options?: {
            handlers?: StreamActionHandlers;
            operation?: JsonObject | null;
            timeoutMs?: number;
        }
    ): StreamActionResult;
    reconnectOperations(): Promise<void>;
    requestTaskCancellation(taskId: string, reason: string | null): Promise<TaskCancellationResponse>;
    hasActiveOperationsOfType(types: string | string[]): boolean;
    getActiveOperationTaskId(operationKey: string): string | null;
}

export type { StreamTaskRuntimeContract };
