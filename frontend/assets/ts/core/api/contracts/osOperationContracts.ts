/* SoAI - Frontend OS operation response contracts [frontend/assets/ts/core/api/contracts/osOperationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';

interface OsDryRunResponse {
    dryRun: true;
    plannedCommands: string[][];
    predictedEffects: string[];
    warnings: string[];
}
interface OsTaskAcceptedResponse {
    status: 'accepted';
    taskId: string;
    commitDeadlineTsMs?: number | undefined;
}
interface OsTaskStatusResponse {
    success: true;
    status: string;
    taskId: string;
}
interface OsBooleanOperationResponse {
    success?: boolean | undefined;
    changed?: boolean | undefined;
    deleted?: boolean | undefined;
    mounted?: boolean | undefined;
    unmounted?: boolean | undefined;
    removed?: boolean | undefined;
    scheduled?: boolean | undefined;
    locked?: boolean | undefined;
    updated?: boolean | undefined;
    released?: boolean | undefined;
}
type OsOperationResponse = OsDryRunResponse | OsTaskAcceptedResponse | OsTaskStatusResponse | OsBooleanOperationResponse;
interface OsDryRunDisplay {
    plannedCommands: string[];
    predictedEffects: string[];
    warnings: string[];
}

const readStringArray = (value: ApiResponsePayload, label: string): string[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => readRequiredStringValue(entry, `${label}[${String(index)}]`));
};

const decodeOsOperationResponse = (value: ApiResponsePayload, label: string): OsOperationResponse => {
    const record = requireRecord(value, label);
    if (record['dry_run'] === true) {
        const commandsValue = record['planned_commands'];
        if (!Array.isArray(commandsValue)) throw new TypeError(`${label}.planned_commands must be an array`);
        return {
            dryRun: true,
            plannedCommands: commandsValue.map((command, index) => readStringArray(command, `${label}.planned_commands[${String(index)}]`)),
            predictedEffects: readStringArray(record['predicted_effects'], `${label}.predicted_effects`),
            warnings: readStringArray(record['warnings'], `${label}.warnings`)
        };
    }
    if (record['status'] === 'accepted') {
        const response: OsTaskAcceptedResponse = { status: 'accepted', taskId: readRequiredStringValue(record['task_id'], `${label}.task_id`) };
        if (record['commit_deadline_ts_ms'] !== undefined) response.commitDeadlineTsMs = readRequiredFiniteNumberValue(record['commit_deadline_ts_ms'], `${label}.commit_deadline_ts_ms`);
        return response;
    }
    if (record['success'] === true && typeof record['status'] === 'string' && record['task_id'] !== undefined) return { success: true, status: record['status'], taskId: readRequiredStringValue(record['task_id'], `${label}.task_id`) };
    const response: OsBooleanOperationResponse = {};
    const booleanFields: readonly (keyof OsBooleanOperationResponse)[] = ['success', 'changed', 'deleted', 'mounted', 'unmounted', 'removed', 'scheduled', 'locked', 'updated', 'released'];
    for (const field of booleanFields) {
        if (record[field] !== undefined) response[field] = readRequiredBooleanValue(record[field], `${label}.${field}`);
    }
    if (Object.keys(response).length === 0) throw new TypeError(`${label} must contain an operation result`);
    return response;
};

const requireOsDryRunResponse = (response: OsOperationResponse, label: string): OsDryRunResponse => {
    if (!('dryRun' in response) || response.dryRun !== true) throw new TypeError(`${label} must be a dry-run response`);
    return response;
};

const toOsDryRunDisplay = (response: OsOperationResponse, label: string): OsDryRunDisplay => {
    const dryRun = requireOsDryRunResponse(response, label);
    return { plannedCommands: dryRun.plannedCommands.map((command) => command.join(' ')), predictedEffects: dryRun.predictedEffects, warnings: dryRun.warnings };
};

const requireOsTaskAcceptedResponse = (response: OsOperationResponse, label: string): OsTaskAcceptedResponse => {
    if (!('status' in response) || response.status !== 'accepted' || 'success' in response) throw new TypeError(`${label} must be an accepted task response`);
    return response;
};

const requireOsSuccessfulResponse = (response: OsOperationResponse, label: string): OsBooleanOperationResponse | OsTaskStatusResponse => {
    if (!('success' in response) || response.success !== true) throw new TypeError(`${label} must be a successful response`);
    return response;
};

export { decodeOsOperationResponse, requireOsDryRunResponse, requireOsSuccessfulResponse, requireOsTaskAcceptedResponse, toOsDryRunDisplay };
export type { OsBooleanOperationResponse, OsDryRunDisplay, OsDryRunResponse, OsOperationResponse, OsTaskAcceptedResponse, OsTaskStatusResponse };
