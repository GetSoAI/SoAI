/* SoAI - Frontend system metrics timing statistics contract [frontend/assets/ts/core/realtime/streammanager/resources/systemMetricsTimingContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { decodeFiniteNumberArray } from '@core/realtime/streammanager/resources/systemMetricsValueDecoding.ts';

const decodeTimingStatistics = (source: JsonObject, wireName: string, label: string): JsonObject | undefined => {
    const value = source[wireName];
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new TypeError(`${label}.${wireName} must be an object`);
    const decoded: JsonObject = {};
    const avg = value['avg'];
    const min = value['min'];
    const max = value['max'];
    const p95 = value['p95'];
    const count = value['count'];
    if (avg !== undefined && avg !== null) {
        if (typeof avg !== 'number' || !Number.isFinite(avg)) throw new TypeError(`${label}.${wireName}.avg must be a finite number`);
        decoded['avg'] = avg;
    }
    if (min !== undefined && min !== null) {
        if (typeof min !== 'number' || !Number.isFinite(min)) throw new TypeError(`${label}.${wireName}.min must be a finite number`);
        decoded['min'] = min;
    }
    if (max !== undefined && max !== null) {
        if (typeof max !== 'number' || !Number.isFinite(max)) throw new TypeError(`${label}.${wireName}.max must be a finite number`);
        decoded['max'] = max;
    }
    if (p95 !== undefined && p95 !== null) {
        if (typeof p95 !== 'number' || !Number.isFinite(p95)) throw new TypeError(`${label}.${wireName}.p95 must be a finite number`);
        decoded['p95'] = p95;
    }
    if (count !== undefined && count !== null) {
        if (typeof count !== 'number' || !Number.isFinite(count)) throw new TypeError(`${label}.${wireName}.count must be a finite number`);
        decoded['count'] = count;
    }
    return decoded;
};

const decodeSystemMetricsTimings = (record: JsonObject, label: string, fieldNames: Readonly<Record<string, string>>): JsonObject | undefined => {
    const value = record['timings'];
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new TypeError(`${label}.timings must be an object`);
    const decoded: JsonObject = {};
    for (const [wireName, domainName] of Object.entries(fieldNames)) {
        const samples = value[wireName];
        if (samples !== undefined && samples !== null) decoded[domainName] = decodeFiniteNumberArray(samples, `${label}.timings.${wireName}`);
        const statistics = decodeTimingStatistics(value, `${wireName}_stats`, `${label}.timings`);
        if (statistics) decoded[`${domainName}Stats`] = statistics;
    }
    return decoded;
};

export { decodeSystemMetricsTimings };
