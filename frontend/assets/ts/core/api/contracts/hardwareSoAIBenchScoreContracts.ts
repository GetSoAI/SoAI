/* SoAI - Shared frontend API contract boundary hardware SoAI bench score contracts [frontend/assets/ts/core/api/contracts/hardwareSoAIBenchScoreContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSoAIBenchScore } from '@core/api/contracts/hardwareSoAIBenchTypes.ts';
import { readSoAIBenchOptionalBoolean, readSoAIBenchOptionalNumber, readSoAIBenchOptionalString, readSoAIBenchOptionalStringList } from '@core/api/contracts/hardwareSoAIBenchReaders.ts';
import { hasOwn } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const decodeGpuSoAIBenchScore = (value: JsonValue | undefined, label: string): GpuSoAIBenchScore | null | undefined => {
    if (value === undefined) return undefined;
    if (value === null) return null;
    if (!isJsonObject(value)) throw new TypeError(`${label} must be an object or null`);
    if (hasOwn(value, 'scoreVersion') || hasOwn(value, 'overallScore') || hasOwn(value, 'sampleCount')) throw new TypeError(`${label} must use canonical V1 wire fields`);
    const decoded: GpuSoAIBenchScore = {};
    const scoreVersion = readSoAIBenchOptionalString(value, 'score_version', label);
    const overallScore = readSoAIBenchOptionalNumber(value, 'overall_score', label);
    const computeScore = readSoAIBenchOptionalNumber(value, 'compute_score', label);
    const memoryScore = readSoAIBenchOptionalNumber(value, 'memory_score', label);
    const latencyScore = readSoAIBenchOptionalNumber(value, 'latency_score', label);
    const stabilityMultiplier = readSoAIBenchOptionalNumber(value, 'stability_multiplier', label);
    const computeGops = readSoAIBenchOptionalNumber(value, 'compute_gops', label);
    const aluGops = readSoAIBenchOptionalNumber(value, 'alu_gops', label);
    const matrixGops = readSoAIBenchOptionalNumber(value, 'matrix_gops', label);
    const memoryGbs = readSoAIBenchOptionalNumber(value, 'memory_gbs', label);
    const latencyUs = readSoAIBenchOptionalNumber(value, 'latency_us', label);
    const latencyDispatchesPerSecond = readSoAIBenchOptionalNumber(value, 'latency_dispatches_per_second', label);
    const durationMs = readSoAIBenchOptionalNumber(value, 'duration_ms', label);
    const sampleCount = readSoAIBenchOptionalNumber(value, 'sample_count', label);
    const maxTemperatureCelsius = readSoAIBenchOptionalNumber(value, 'max_temperature_celsius', label);
    const avgPowerWatts = readSoAIBenchOptionalNumber(value, 'avg_power_watts', label);
    const maxPowerWatts = readSoAIBenchOptionalNumber(value, 'max_power_watts', label);
    const coreUtilizationPercent = readSoAIBenchOptionalNumber(value, 'core_utilization_percent', label);
    const throttleDetected = readSoAIBenchOptionalBoolean(value, 'throttle_detected', label);
    const telemetryAvailable = readSoAIBenchOptionalBoolean(value, 'telemetry_available', label);
    const unavailableSensors = readSoAIBenchOptionalStringList(value, 'unavailable_sensors', label);
    const failureReason = readSoAIBenchOptionalString(value, 'failure_reason', label);
    const scoreVariancePercent = readSoAIBenchOptionalNumber(value, 'score_variance_percent', label);
    const scoreConfidence = readSoAIBenchOptionalString(value, 'score_confidence', label);
    if (scoreVersion !== undefined) decoded.scoreVersion = scoreVersion;
    if (overallScore !== undefined) decoded.overallScore = overallScore;
    if (computeScore !== undefined) decoded.computeScore = computeScore;
    if (memoryScore !== undefined) decoded.memoryScore = memoryScore;
    if (latencyScore !== undefined) decoded.latencyScore = latencyScore;
    if (stabilityMultiplier !== undefined) decoded.stabilityMultiplier = stabilityMultiplier;
    if (computeGops !== undefined) decoded.computeGops = computeGops;
    if (aluGops !== undefined) decoded.aluGops = aluGops;
    if (matrixGops !== undefined) decoded.matrixGops = matrixGops;
    if (memoryGbs !== undefined) decoded.memoryGbs = memoryGbs;
    if (latencyUs !== undefined) decoded.latencyUs = latencyUs;
    if (latencyDispatchesPerSecond !== undefined) decoded.latencyDispatchesPerSecond = latencyDispatchesPerSecond;
    if (durationMs !== undefined) decoded.durationMs = durationMs;
    if (sampleCount !== undefined) decoded.sampleCount = sampleCount;
    if (maxTemperatureCelsius !== undefined) decoded.maxTemperatureCelsius = maxTemperatureCelsius;
    if (avgPowerWatts !== undefined) decoded.avgPowerWatts = avgPowerWatts;
    if (maxPowerWatts !== undefined) decoded.maxPowerWatts = maxPowerWatts;
    if (coreUtilizationPercent !== undefined) decoded.coreUtilizationPercent = coreUtilizationPercent;
    if (throttleDetected !== undefined) decoded.throttleDetected = throttleDetected;
    if (telemetryAvailable !== undefined) decoded.telemetryAvailable = telemetryAvailable;
    if (unavailableSensors !== undefined) decoded.unavailableSensors = unavailableSensors;
    if (failureReason !== undefined) decoded.failureReason = failureReason;
    if (scoreVariancePercent !== undefined) decoded.scoreVariancePercent = scoreVariancePercent;
    if (scoreConfidence !== undefined) decoded.scoreConfidence = scoreConfidence;
    return decoded;
};

const serializeGpuSoAIBenchScore = (score: GpuSoAIBenchScore | null): JsonObject | null => {
    if (score === null) return null;
    return {
        ...(score.scoreVersion !== undefined ? { 'score_version': score.scoreVersion } : {}),
        ...(score.overallScore !== undefined ? { 'overall_score': score.overallScore } : {}),
        ...(score.computeScore !== undefined ? { 'compute_score': score.computeScore } : {}),
        ...(score.memoryScore !== undefined ? { 'memory_score': score.memoryScore } : {}),
        ...(score.latencyScore !== undefined ? { 'latency_score': score.latencyScore } : {}),
        ...(score.stabilityMultiplier !== undefined ? { 'stability_multiplier': score.stabilityMultiplier } : {}),
        ...(score.computeGops !== undefined ? { 'compute_gops': score.computeGops } : {}),
        ...(score.aluGops !== undefined ? { 'alu_gops': score.aluGops } : {}),
        ...(score.matrixGops !== undefined ? { 'matrix_gops': score.matrixGops } : {}),
        ...(score.memoryGbs !== undefined ? { 'memory_gbs': score.memoryGbs } : {}),
        ...(score.latencyUs !== undefined ? { 'latency_us': score.latencyUs } : {}),
        ...(score.latencyDispatchesPerSecond !== undefined ? { 'latency_dispatches_per_second': score.latencyDispatchesPerSecond } : {}),
        ...(score.durationMs !== undefined ? { 'duration_ms': score.durationMs } : {}),
        ...(score.sampleCount !== undefined ? { 'sample_count': score.sampleCount } : {}),
        ...(score.maxTemperatureCelsius !== undefined ? { 'max_temperature_celsius': score.maxTemperatureCelsius } : {}),
        ...(score.avgPowerWatts !== undefined ? { 'avg_power_watts': score.avgPowerWatts } : {}),
        ...(score.maxPowerWatts !== undefined ? { 'max_power_watts': score.maxPowerWatts } : {}),
        ...(score.coreUtilizationPercent !== undefined ? { 'core_utilization_percent': score.coreUtilizationPercent } : {}),
        ...(score.throttleDetected !== undefined ? { 'throttle_detected': score.throttleDetected } : {}),
        ...(score.telemetryAvailable !== undefined ? { 'telemetry_available': score.telemetryAvailable } : {}),
        ...(score.unavailableSensors !== undefined ? { 'unavailable_sensors': score.unavailableSensors } : {}),
        ...(score.failureReason !== undefined ? { 'failure_reason': score.failureReason } : {}),
        ...(score.scoreVariancePercent !== undefined ? { 'score_variance_percent': score.scoreVariancePercent } : {}),
        ...(score.scoreConfidence !== undefined ? { 'score_confidence': score.scoreConfidence } : {})
    };
};

export { decodeGpuSoAIBenchScore, serializeGpuSoAIBenchScore };
