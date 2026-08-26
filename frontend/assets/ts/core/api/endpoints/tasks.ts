/* SoAI - Shared API tasks [frontend/assets/ts/core/api/endpoints/tasks.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildSignalRequestOptions } from '@core/api/requestOptions.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ApiQueryParameters, RequestOptions } from '@core/api/types/request.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { decodeTaskListResponse, decodeTaskResponse, type TaskListResponse, type TaskResponse } from '@core/api/contracts/taskContracts.ts';

interface ListActiveTasksOptions {
    taskType?: string;
    limit?: number;
    signal?: AbortSignal;
}

const createTasksEndpoints = (api: ApiClientContext): { listActive: (options?: ListActiveTasksOptions) => Promise<TaskListResponse>; get: (taskId: string, options?: RequestOptions) => Promise<TaskResponse> } => {
    return {
        listActive: async (options: ListActiveTasksOptions = {}): Promise<TaskListResponse> => {
            const query: ApiQueryParameters = {};
            const taskType = toTrimmedString(options.taskType);
            if (taskType) {
                query['task_type'] = taskType;
            }
            if (Number.isFinite(options.limit)) {
                query['limit'] = options.limit;
            }
            return decodeTaskListResponse(await api.get('/api/v1/tasks/active', { query, ...buildSignalRequestOptions(options) }));
        },
        get: async (taskId: string, options: RequestOptions = {}): Promise<TaskResponse> => {
            const trimmed = toTrimmedString(taskId);
            if (!trimmed) {
                throw new Error('tasks.get requires a taskId');
            }
            return decodeTaskResponse(await api.get(`/api/v1/tasks/${api.encodePathSegment(trimmed)}`, options));
        }
    };
};

export { createTasksEndpoints };
