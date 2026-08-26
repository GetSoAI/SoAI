/* SoAI - Hardware feature SoAI Bench runs index [frontend/assets/ts/features/hardware/soaibenchRunsIndex.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { requireDecodedSoAIBenchRun, type DecodedSoAIBenchRun } from '@core/realtime/streammanager/resources/soaibenchRunsResource.ts';

const getSoAIBenchRunsForDevice = (payload: JsonValue | null | undefined, deviceId: string | null): readonly DecodedSoAIBenchRun[] => {
    const normalizedDeviceId = toTrimmedString(deviceId);
    if (!normalizedDeviceId || isNullOrUndefined(payload)) {
        return [];
    }
    if (!isJsonObject(payload)) {
        throw new TypeError('SoAIBench runs payload must be an object');
    }
    const byDevice = payload['byDeviceId'];
    if (!isJsonObject(byDevice)) {
        throw new TypeError('SoAIBench runs payload must include byDeviceId');
    }
    const runs = byDevice[normalizedDeviceId];
    if (runs === undefined) {
        return [];
    }
    if (!Array.isArray(runs)) {
        throw new TypeError('SoAIBench runs byDeviceId entry must be an array');
    }
    return runs.map((run, index) => requireDecodedSoAIBenchRun(run, `SoAIBench runs byDeviceId entry ${String(index)}`));
};

const getSoAIBenchRunById = (payload: JsonValue | null | undefined, runId: string | null): DecodedSoAIBenchRun | null => {
    const normalizedRunId = toTrimmedString(runId);
    if (!normalizedRunId || isNullOrUndefined(payload)) {
        return null;
    }
    if (!isJsonObject(payload)) {
        throw new TypeError('SoAIBench runs payload must be an object');
    }
    const byRun = payload['byRunId'];
    if (!isJsonObject(byRun)) {
        throw new TypeError('SoAIBench runs payload must include byRunId');
    }
    const run = byRun[normalizedRunId];
    if (run === undefined) {
        return null;
    }
    return requireDecodedSoAIBenchRun(run, 'SoAIBench runs byRunId entry');
};

const hasSoAIBenchHistoryForDevice = (payload: JsonValue | null | undefined, deviceId: string | null): boolean => {
    return getSoAIBenchRunsForDevice(payload, deviceId).length > 0;
};

export { getSoAIBenchRunById, getSoAIBenchRunsForDevice, hasSoAIBenchHistoryForDevice };
