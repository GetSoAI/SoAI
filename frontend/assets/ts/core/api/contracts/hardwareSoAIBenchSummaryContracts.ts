/* SoAI - Shared frontend API contract boundary hardware SoAI bench summary contracts [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchSummaryContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readSoAIBenchOptionalBoolean, readSoAIBenchOptionalNumber, readSoAIBenchOptionalString, readSoAIBenchOptionalStringList } from '@core/api/contracts/hardwareSoAIBenchReaders.ts';
import type { GpuSoAIBenchSummary } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import { hasOwn } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const assignNumber = (source: JsonObject, target: JsonObject, wireKey: string, domainKey: string, label: string): void => {
    const value = readSoAIBenchOptionalNumber(source, wireKey, label);
    if (value !== undefined) target[domainKey] = value;
};

const assignString = (source: JsonObject, target: JsonObject, wireKey: string, domainKey: string, label: string): void => {
    const value = readSoAIBenchOptionalString(source, wireKey, label);
    if (value !== undefined) target[domainKey] = value;
};

const assignBoolean = (source: JsonObject, target: JsonObject, wireKey: string, domainKey: string, label: string): void => {
    const value = readSoAIBenchOptionalBoolean(source, wireKey, label);
    if (value !== undefined) target[domainKey] = value;
};

const assignStringList = (source: JsonObject, target: JsonObject, wireKey: string, domainKey: string, label: string): void => {
    const value = readSoAIBenchOptionalStringList(source, wireKey, label);
    if (value !== undefined) target[domainKey] = value;
};

const decodeWorkloadPhase = (source: JsonObject, target: JsonObject, wirePrefix: string, domainPrefix: string, label: string): void => {
    assignNumber(source, target, `${wirePrefix}_checksum`, `${domainPrefix}Checksum`, label);
    assignNumber(source, target, `${wirePrefix}_elements`, `${domainPrefix}Elements`, label);
    assignNumber(source, target, `${wirePrefix}_requested_elements`, `${domainPrefix}RequestedElements`, label);
    assignNumber(source, target, `${wirePrefix}_allocation_bytes`, `${domainPrefix}AllocationBytes`, label);
    assignNumber(source, target, `${wirePrefix}_checksum_sample_count`, `${domainPrefix}ChecksumSampleCount`, label);
};

const decodeGpuSoAIBenchSummary = (value: JsonValue | undefined, label: string): GpuSoAIBenchSummary | undefined => {
    if (value === undefined || value === null) return undefined;
    if (!isJsonObject(value)) throw new TypeError(`${label} must be an object`);
    if (hasOwn(value, 'progressPercent') || hasOwn(value, 'currentPhase') || hasOwn(value, 'overallScore')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const decoded: GpuSoAIBenchSummary = {};
    assignNumber(value, decoded, 'overall_score', 'overallScore', label);
    assignNumber(value, decoded, 'compute_score', 'computeScore', label);
    assignNumber(value, decoded, 'compute_gops', 'computeGops', label);
    assignNumber(value, decoded, 'alu_gops', 'aluGops', label);
    assignNumber(value, decoded, 'matrix_gops', 'matrixGops', label);
    assignNumber(value, decoded, 'memory_score', 'memoryScore', label);
    assignNumber(value, decoded, 'memory_gbs', 'memoryGbs', label);
    assignNumber(value, decoded, 'latency_score', 'latencyScore', label);
    assignNumber(value, decoded, 'latency_us', 'latencyUs', label);
    assignNumber(value, decoded, 'latency_dispatches_per_second', 'latencyDispatchesPerSecond', label);
    assignNumber(value, decoded, 'duration_ms', 'durationMs', label);
    assignNumber(value, decoded, 'sample_count', 'sampleCount', label);
    assignNumber(value, decoded, 'score_variance_percent', 'scoreVariancePercent', label);
    assignNumber(value, decoded, 'temperature_limit_celsius', 'temperatureLimitCelsius', label);
    assignNumber(value, decoded, 'temperature_celsius', 'temperatureCelsius', label);
    assignNumber(value, decoded, 'max_temperature_celsius', 'maxTemperatureCelsius', label);
    assignNumber(value, decoded, 'avg_power_watts', 'avgPowerWatts', label);
    assignNumber(value, decoded, 'power_draw_watts', 'powerDrawWatts', label);
    assignNumber(value, decoded, 'max_power_watts', 'maxPowerWatts', label);
    assignNumber(value, decoded, 'core_utilization_percent', 'coreUtilizationPercent', label);
    assignNumber(value, decoded, 'utilization', 'utilization', label);
    assignNumber(value, decoded, 'warmup_passes_completed', 'warmupPassesCompleted', label);
    assignNumber(value, decoded, 'measured_passes_completed', 'measuredPassesCompleted', label);
    assignNumber(value, decoded, 'current_pass_index', 'currentPassIndex', label);
    assignNumber(value, decoded, 'current_pass_total', 'currentPassTotal', label);
    assignNumber(value, decoded, 'current_phase_index', 'currentPhaseIndex', label);
    assignNumber(value, decoded, 'current_phase_total', 'currentPhaseTotal', label);
    assignNumber(value, decoded, 'progress_percent', 'progressPercent', label);
    assignNumber(value, decoded, 'stress_sample_count', 'stressSampleCount', label);
    assignNumber(value, decoded, 'opencl_global_mem_bytes', 'openclGlobalMemBytes', label);
    assignNumber(value, decoded, 'opencl_max_alloc_bytes', 'openclMaxAllocBytes', label);
    assignString(value, decoded, 'benchmark_mode', 'benchmarkMode', label);
    assignString(value, decoded, 'current_pass_type', 'currentPassType', label);
    assignString(value, decoded, 'current_phase', 'currentPhase', label);
    assignString(value, decoded, 'temperature_warning', 'temperatureWarning', label);
    assignString(value, decoded, 'match_basis', 'matchBasis', label);
    assignString(value, decoded, 'queue_api', 'queueApi', label);
    assignString(value, decoded, 'opencl_platform_name', 'openclPlatformName', label);
    assignString(value, decoded, 'opencl_platform_vendor', 'openclPlatformVendor', label);
    assignString(value, decoded, 'opencl_device_name', 'openclDeviceName', label);
    assignString(value, decoded, 'opencl_device_vendor', 'openclDeviceVendor', label);
    assignString(value, decoded, 'opencl_driver_version', 'openclDriverVersion', label);
    assignString(value, decoded, 'leaderboard_rejection_reason', 'leaderboardRejectionReason', label);
    assignNumber(value, decoded, 'score_confidence', 'scoreConfidence', label);
    assignString(value, decoded, 'message', 'message', label);
    assignString(value, decoded, 'guidance', 'guidance', label);
    assignBoolean(value, decoded, 'telemetry_available', 'telemetryAvailable', label);
    assignBoolean(value, decoded, 'throttle_detected', 'throttleDetected', label);
    assignBoolean(value, decoded, 'leaderboard_eligible', 'leaderboardEligible', label);
    assignStringList(value, decoded, 'unavailable_sensors', 'unavailableSensors', label);
    decodeWorkloadPhase(value, decoded, 'alu', 'alu', label);
    decodeWorkloadPhase(value, decoded, 'compute', 'compute', label);
    decodeWorkloadPhase(value, decoded, 'matrix', 'matrix', label);
    decodeWorkloadPhase(value, decoded, 'latency', 'latency', label);
    decodeWorkloadPhase(value, decoded, 'memory', 'memory', label);
    decodeWorkloadPhase(value, decoded, 'mixed', 'mixed', label);
    return decoded;
};

const assignWireValue = (source: GpuSoAIBenchSummary, target: JsonObject, domainKey: string, wireKey: string): void => {
    if (hasOwn(source, domainKey)) target[wireKey] = source[domainKey] ?? null;
};

const serializeWorkloadPhase = (source: GpuSoAIBenchSummary, target: JsonObject, domainPrefix: string, wirePrefix: string): void => {
    assignWireValue(source, target, `${domainPrefix}Checksum`, `${wirePrefix}_checksum`);
    assignWireValue(source, target, `${domainPrefix}Elements`, `${wirePrefix}_elements`);
    assignWireValue(source, target, `${domainPrefix}RequestedElements`, `${wirePrefix}_requested_elements`);
    assignWireValue(source, target, `${domainPrefix}AllocationBytes`, `${wirePrefix}_allocation_bytes`);
    assignWireValue(source, target, `${domainPrefix}ChecksumSampleCount`, `${wirePrefix}_checksum_sample_count`);
};

const serializeGpuSoAIBenchSummary = (summary: GpuSoAIBenchSummary): JsonObject => {
    const wire: JsonObject = {};
    assignWireValue(summary, wire, 'overallScore', 'overall_score');
    assignWireValue(summary, wire, 'computeScore', 'compute_score');
    assignWireValue(summary, wire, 'computeGops', 'compute_gops');
    assignWireValue(summary, wire, 'aluGops', 'alu_gops');
    assignWireValue(summary, wire, 'matrixGops', 'matrix_gops');
    assignWireValue(summary, wire, 'memoryScore', 'memory_score');
    assignWireValue(summary, wire, 'memoryGbs', 'memory_gbs');
    assignWireValue(summary, wire, 'latencyScore', 'latency_score');
    assignWireValue(summary, wire, 'latencyUs', 'latency_us');
    assignWireValue(summary, wire, 'latencyDispatchesPerSecond', 'latency_dispatches_per_second');
    assignWireValue(summary, wire, 'durationMs', 'duration_ms');
    assignWireValue(summary, wire, 'sampleCount', 'sample_count');
    assignWireValue(summary, wire, 'scoreVariancePercent', 'score_variance_percent');
    assignWireValue(summary, wire, 'temperatureLimitCelsius', 'temperature_limit_celsius');
    assignWireValue(summary, wire, 'temperatureCelsius', 'temperature_celsius');
    assignWireValue(summary, wire, 'maxTemperatureCelsius', 'max_temperature_celsius');
    assignWireValue(summary, wire, 'avgPowerWatts', 'avg_power_watts');
    assignWireValue(summary, wire, 'powerDrawWatts', 'power_draw_watts');
    assignWireValue(summary, wire, 'maxPowerWatts', 'max_power_watts');
    assignWireValue(summary, wire, 'coreUtilizationPercent', 'core_utilization_percent');
    assignWireValue(summary, wire, 'utilization', 'utilization');
    assignWireValue(summary, wire, 'warmupPassesCompleted', 'warmup_passes_completed');
    assignWireValue(summary, wire, 'measuredPassesCompleted', 'measured_passes_completed');
    assignWireValue(summary, wire, 'currentPassType', 'current_pass_type');
    assignWireValue(summary, wire, 'currentPassIndex', 'current_pass_index');
    assignWireValue(summary, wire, 'currentPassTotal', 'current_pass_total');
    assignWireValue(summary, wire, 'currentPhase', 'current_phase');
    assignWireValue(summary, wire, 'currentPhaseIndex', 'current_phase_index');
    assignWireValue(summary, wire, 'currentPhaseTotal', 'current_phase_total');
    assignWireValue(summary, wire, 'progressPercent', 'progress_percent');
    assignWireValue(summary, wire, 'stressSampleCount', 'stress_sample_count');
    assignWireValue(summary, wire, 'benchmarkMode', 'benchmark_mode');
    assignWireValue(summary, wire, 'temperatureWarning', 'temperature_warning');
    assignWireValue(summary, wire, 'matchBasis', 'match_basis');
    assignWireValue(summary, wire, 'queueApi', 'queue_api');
    assignWireValue(summary, wire, 'openclPlatformName', 'opencl_platform_name');
    assignWireValue(summary, wire, 'openclPlatformVendor', 'opencl_platform_vendor');
    assignWireValue(summary, wire, 'openclDeviceName', 'opencl_device_name');
    assignWireValue(summary, wire, 'openclDeviceVendor', 'opencl_device_vendor');
    assignWireValue(summary, wire, 'openclDriverVersion', 'opencl_driver_version');
    assignWireValue(summary, wire, 'openclGlobalMemBytes', 'opencl_global_mem_bytes');
    assignWireValue(summary, wire, 'openclMaxAllocBytes', 'opencl_max_alloc_bytes');
    assignWireValue(summary, wire, 'leaderboardEligible', 'leaderboard_eligible');
    assignWireValue(summary, wire, 'leaderboardRejectionReason', 'leaderboard_rejection_reason');
    assignWireValue(summary, wire, 'scoreConfidence', 'score_confidence');
    assignWireValue(summary, wire, 'message', 'message');
    assignWireValue(summary, wire, 'guidance', 'guidance');
    assignWireValue(summary, wire, 'telemetryAvailable', 'telemetry_available');
    assignWireValue(summary, wire, 'throttleDetected', 'throttle_detected');
    assignWireValue(summary, wire, 'unavailableSensors', 'unavailable_sensors');
    serializeWorkloadPhase(summary, wire, 'alu', 'alu');
    serializeWorkloadPhase(summary, wire, 'compute', 'compute');
    serializeWorkloadPhase(summary, wire, 'matrix', 'matrix');
    serializeWorkloadPhase(summary, wire, 'latency', 'latency');
    serializeWorkloadPhase(summary, wire, 'memory', 'memory');
    serializeWorkloadPhase(summary, wire, 'mixed', 'mixed');
    return wire;
};

export { decodeGpuSoAIBenchSummary, serializeGpuSoAIBenchSummary };
