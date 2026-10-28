/* SoAI - Hardware component observation contracts [frontend/assets/ts/core/api/contracts/hardwareComponentObservationContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { ReconciledResourceStatus } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';

interface HardwareComponentObservation {
    status: 'available' | 'partial' | 'stale' | 'unavailable' | 'disconnected';
    observedAtMs: number | null;
    checkedAtMs: number;
    errorCode?: string | undefined;
    sampledCurrent?: boolean | undefined;
    source?: string | undefined;
}
interface HardwareObservationSnapshot {
    componentStatus?: Record<string, HardwareComponentObservation> | undefined;
    timestampMs?: number | undefined;
    capabilities?: { monitoringIntervalMs?: number | undefined } | undefined;
}

const decodeHardwareComponentObservation = (value: JsonValue, label: string): HardwareComponentObservation => {
    const record = requireRecord(value, label);
    const status = record['status'];
    if (status !== 'available' && status !== 'partial' && status !== 'stale' && status !== 'unavailable' && status !== 'disconnected') throw new TypeError(`${label}.status is invalid`);
    const observedAtMs = record['observed_at_ms'] === null ? null : readRequiredNonNegativeIntegerValue(record['observed_at_ms'], `${label}.observed_at_ms`);
    const checkedAtMs = readRequiredNonNegativeIntegerValue(record['checked_at_ms'], `${label}.checked_at_ms`);
    if ((status === 'available' || status === 'partial') && observedAtMs === null) throw new TypeError(`${label} has no observation timestamp`);
    const observation: HardwareComponentObservation = { status, observedAtMs, checkedAtMs };
    if (record['source'] !== undefined && record['source'] !== null) {
        if (typeof record['source'] !== 'string' || !record['source'].trim()) throw new TypeError(`${label}.source is invalid`);
        observation.source = record['source'];
    }
    if (record['sampled_current'] !== undefined) {
        if (typeof record['sampled_current'] !== 'boolean') throw new TypeError(`${label}.sampled_current is invalid`);
        observation.sampledCurrent = record['sampled_current'];
    }
    if (record['error_code'] !== undefined) {
        if (typeof record['error_code'] !== 'string' || !record['error_code'].trim()) throw new TypeError(`${label}.error_code is invalid`);
        observation.errorCode = record['error_code'];
    }
    if (record['failed_item_count'] !== undefined) readRequiredNonNegativeIntegerValue(record['failed_item_count'], `${label}.failed_item_count`);
    if (record['diagnostics'] !== undefined) {
        if (!Array.isArray(record['diagnostics'])) throw new TypeError(`${label}.diagnostics must be an array`);
        for (const diagnostic of record['diagnostics']) {
            const item = requireRecord(diagnostic, `${label}.diagnostics item`);
            if (typeof item['scope'] !== 'string' || !item['scope'].trim() || typeof item['reason'] !== 'string' || !item['reason'].trim()) throw new TypeError(`${label}.diagnostics item is invalid`);
            if (item['item_index'] !== undefined && item['item_index'] !== null) readRequiredNonNegativeIntegerValue(item['item_index'], `${label}.diagnostics.item_index`);
        }
    }
    return observation;
};

const decodeHardwareComponentStatuses = (value: JsonValue | undefined): Record<string, HardwareComponentObservation> | undefined => {
    if (value === undefined) return undefined;
    return Object.fromEntries(Object.entries(requireRecord(value, 'Hardware component_status')).map(([component, observation]) => [component, decodeHardwareComponentObservation(observation, `Hardware component_status.${component}`)]));
};

const isHardwareObservationFresh = (observation: HardwareComponentObservation | undefined): boolean => observation === undefined || observation.status === 'available' || observation.status === 'partial';

const isCurrentHardwareObservationSample = (observation: HardwareComponentObservation | undefined, aggregateTimestamp: number | undefined): boolean => {
    if (!isHardwareObservationFresh(observation)) return false;
    return observation === undefined || (observation.sampledCurrent ?? observation.observedAtMs === aggregateTimestamp);
};

const resolveHardwareObservation = (snapshot: HardwareObservationSnapshot, component: string, row?: HardwareComponentObservation): HardwareComponentObservation | undefined => {
    const whole = snapshot.componentStatus?.[component];
    return whole && !isHardwareObservationFresh(whole) ? whole : (row ?? whole);
};

const shouldDimHardwareObservation = (observation: HardwareComponentObservation | undefined, consecutiveStale: number, now: number, intervalMs: number): boolean => {
    if (isHardwareObservationFresh(observation)) return false;
    return consecutiveStale >= 3 || (observation?.observedAtMs !== null && observation?.observedAtMs !== undefined && now - observation.observedAtMs >= 3 * intervalMs);
};

const projectHardwareResourceObservation = (value: JsonValue | null, status: ReconciledResourceStatus, checkedAtMs: number): JsonValue | null => {
    if (status === 'ready' || !isJsonObject(value)) return value;
    const previousStatuses = isJsonObject(value['componentStatus']) ? value['componentStatus'] : {};
    const componentStatus: JsonObject = {};
    const components: Readonly<Record<string, string>> = { cpus: 'cpus', cpu: 'cpu', memory: 'memory', swap: 'swap', gpu: 'gpu', disk: 'disk', network: 'network', networkSpeed: 'network_speed', diskSpeed: 'disk_speed', uptime: 'uptime', os: 'os' };
    for (const component of new Set([
        ...Object.keys(previousStatuses),
        ...Object.keys(value)
            .map((key) => components[key])
            .filter((key): key is string => key !== undefined)
    ])) {
        const previous = previousStatuses[component];
        componentStatus[component] = {
            ...(isJsonObject(previous) ? previous : {}),
            status: status === 'disconnected' ? 'disconnected' : 'stale',
            observedAtMs: isJsonObject(previous) ? (previous['observedAtMs'] ?? null) : (value['timestampMs'] ?? null),
            checkedAtMs,
            sampledCurrent: false
        };
    }
    return { ...value, componentStatus };
};

export { isCurrentHardwareObservationSample, decodeHardwareComponentObservation, decodeHardwareComponentStatuses, isHardwareObservationFresh, projectHardwareResourceObservation, resolveHardwareObservation, shouldDimHardwareObservation };
export type { HardwareComponentObservation, HardwareObservationSnapshot };
