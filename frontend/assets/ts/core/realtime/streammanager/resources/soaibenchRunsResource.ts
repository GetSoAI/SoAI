/* SoAI - Shared frontend realtime stream manager resources SoAI Bench runs resource [frontend/assets/ts/core/realtime/streammanager/resources/soaibenchRunsResource.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { decodeGpuSoAIBenchRun, type GpuSoAIBenchRun } from '@core/api/contracts/hardwareContracts.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { ResourceContext, ResourceRegistrationConfig } from '@core/realtime/streammanager/types.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isArray, isFiniteNumber, isObject, isPlainObject } from '@core/typeGuards.ts';

type DecodedSoAIBenchRun = JsonObject &
    GpuSoAIBenchRun & {
        runId: string;
        deviceId: string;
        status: string;
        updateSeq: number;
    };

type SoAIBenchRunsState = JsonObject & {
    runs: DecodedSoAIBenchRun[];
    byRunId: Record<string, DecodedSoAIBenchRun>;
    byDeviceId: Record<string, DecodedSoAIBenchRun[]>;
    deletedSeqByRunId: Record<string, number>;
};

const createEmptyState = (): SoAIBenchRunsState => ({
    runs: [],
    byRunId: {},
    byDeviceId: {},
    deletedSeqByRunId: {}
});

const normalizeNonNegativeInteger = (value: number | null | undefined): number => {
    if (isFiniteNumber(value) && Number.isInteger(value) && value >= 0) {
        return value;
    }
    return 0;
};

const isDecodedSoAIBenchRun = (value: JsonValue | null | undefined): value is DecodedSoAIBenchRun => {
    return isJsonObject(value) && typeof value['runId'] === 'string' && typeof value['deviceId'] === 'string' && typeof value['status'] === 'string' && isFiniteNumber(value['updateSeq']);
};

const requireDecodedSoAIBenchRun = (value: JsonValue | null | undefined, label: string): DecodedSoAIBenchRun => {
    if (!isDecodedSoAIBenchRun(value)) {
        throw new TypeError(`${label} must be a decoded SoAIBench run`);
    }
    return value;
};

const normalizeRun = (value: JsonValue | undefined): DecodedSoAIBenchRun => {
    if (value === undefined) {
        throw new TypeError('SoAIBench run payload must be an object');
    }
    const decoded = decodeGpuSoAIBenchRun(value, 'SoAIBench run payload');
    const runId = toTrimmedString(decoded.runId);
    const deviceId = toTrimmedString(decoded.deviceId);
    const status = toTrimmedString(decoded.status);
    if (!runId) {
        throw new TypeError('SoAIBench run payload must include run_id');
    }
    if (!deviceId) {
        throw new TypeError('SoAIBench run payload must include device_id');
    }
    if (!status) {
        throw new TypeError('SoAIBench run payload must include status');
    }
    if (decoded.updateSeq === undefined) {
        throw new TypeError('SoAIBench run payload must include update_seq');
    }
    const run = toJsonCompatibleValue({
        ...decoded,
        runId,
        deviceId,
        status,
        updateSeq: decoded.updateSeq
    });
    return requireDecodedSoAIBenchRun(run, 'SoAIBench run payload');
};

const buildState = (runs: DecodedSoAIBenchRun[], deletedSeqByRunId: Record<string, number> = {}): SoAIBenchRunsState => {
    const byRunId: Record<string, DecodedSoAIBenchRun> = {};
    const byDeviceId: Record<string, DecodedSoAIBenchRun[]> = {};
    const sorted = [...runs].sort((left, right) => {
        const rightStarted = normalizeNonNegativeInteger(right.startedAtMs);
        const leftStarted = normalizeNonNegativeInteger(left.startedAtMs);
        return rightStarted - leftStarted;
    });
    for (const run of sorted) {
        byRunId[run.runId] = run;
        const deviceRuns = byDeviceId[run.deviceId] ?? [];
        deviceRuns.push(run);
        byDeviceId[run.deviceId] = deviceRuns;
    }
    return { runs: sorted, byRunId, byDeviceId, deletedSeqByRunId };
};

const normalizeSnapshot = (payload: JsonValue | null | undefined, previousValue: JsonValue | null | undefined): SoAIBenchRunsState => {
    const record = isPlainObject(payload) ? payload : null;
    if (!record) {
        throw new TypeError('SoAIBench runs snapshot must be an object');
    }
    if (record['success'] === false) {
        throw new Error('SoAIBench runs snapshot failed');
    }
    const rawRuns = record['runs'];
    if (!isArray(rawRuns)) {
        throw new TypeError('SoAIBench runs snapshot must include runs');
    }
    const previous = isSoAIBenchRunsState(previousValue) ? previousValue : createEmptyState();
    const decodedRuns = rawRuns.map((run) => normalizeRun(run));
    const snapshotRunIds = new Set(decodedRuns.map((run) => run.runId));
    const pendingDeletedSeqByRunId: Record<string, number> = {};
    for (const [runId, updateSeq] of Object.entries(previous.deletedSeqByRunId)) {
        if (snapshotRunIds.has(runId)) {
            pendingDeletedSeqByRunId[runId] = updateSeq;
        }
    }
    const runs = decodedRuns.filter((run) => !hasOwn(pendingDeletedSeqByRunId, run.runId));
    return buildState(runs, pendingDeletedSeqByRunId);
};

const normalizePush = (payload: JsonValue | null | undefined, previousValue: JsonValue | null | undefined): SoAIBenchRunsState => {
    const event = isPlainObject(payload) ? payload : null;
    if (!event || !hasOwn(event, 'run')) {
        throw new TypeError('SoAIBench run update must include run');
    }
    const run = normalizeRun(event['run']);
    const previous = isSoAIBenchRunsState(previousValue) ? previousValue : createEmptyState();
    const existing = previous.byRunId[run.runId] ?? null;
    const eventUpdateType = toTrimmedString(event['update_type']);
    if (eventUpdateType === 'local_deleted') {
        const deletedSeqByRunId = {
            ...previous.deletedSeqByRunId,
            [run.runId]: Math.max(run.updateSeq, existing?.updateSeq ?? 0)
        };
        return buildState(
            previous.runs.filter((candidate) => candidate.runId !== run.runId),
            deletedSeqByRunId
        );
    }
    if (hasOwn(previous.deletedSeqByRunId, run.runId)) {
        return previous;
    }
    if (existing && run.updateSeq <= existing.updateSeq) {
        return previous;
    }
    const nextRuns = previous.runs.filter((candidate) => candidate.runId !== run.runId);
    nextRuns.push(run);
    return buildState(nextRuns, { ...previous.deletedSeqByRunId });
};

const isSoAIBenchRunsState = (value: JsonValue | null | undefined): value is SoAIBenchRunsState => {
    return isObject(value) && isArray(value['runs']) && isPlainObject(value['byRunId']) && isPlainObject(value['byDeviceId']) && isPlainObject(value['deletedSeqByRunId']);
};

const createSoAIBenchRunsResource = (): ResourceRegistrationConfig<SoAIBenchRunsState> => ({
    initialValue: createEmptyState(),
    websocketOnly: true,
    normalize: (payload: JsonValue | null, context?: ResourceContext): JsonValue | null => {
        const updateType = toTrimmedString(context?.type);
        if (updateType === 'websocket-push') {
            const next = normalizePush(payload, context?.previousValue);
            return next === context?.previousValue ? next : toJsonCompatibleValue(next);
        }
        return toJsonCompatibleValue(normalizeSnapshot(payload, context?.previousValue));
    }
});

export { createSoAIBenchRunsResource, isDecodedSoAIBenchRun, requireDecodedSoAIBenchRun };
export type { DecodedSoAIBenchRun, SoAIBenchRunsState };
