/* SoAI - Hardware feature widgets mapping [frontend/assets/ts/features/hardware/widgets/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { resolveHardwareDeviceDisplayName } from '@features/hardware/deviceNames.ts';
import { DEFAULT_IGNORED_NETWORK_PREFIXES } from '@features/hardware/models/constants.ts';
import { getCpuDevices, getGpuDevices, getNetworkInterfaces } from '@features/hardware/models/mappers.ts';
import { resolveNetworkSpeedEntry } from '@features/hardware/models/networkSpeed.ts';
import { resolveMemoryValuesMb, type MemoryValues } from '@features/hardware/widgets/metricValues.ts';
import type { MetricChartNormalizer } from '@features/hardware/widgets/contracts.ts';
import type { CPUDevice, CPUDeviceData, GPUDevice, GPUDeviceData, HardwareData, HardwareSnapshot, MemoryData, NetworkDevice, NetworkDeviceData } from '@features/hardware/widgets/internalContracts.ts';
import type { CpuRaw, NetworkInterfaceRaw, NetworkSpeedEntry } from '@features/hardware/models/types.ts';
import type { HardwareGpuSnapshot } from '@core/api/contracts/hardwareContracts.ts';

interface ChartPoint {
    x: number;
    y: number;
}

const readNonEmptyString = (value: string | null | undefined): string | null => toTrimmedStringOrNull(value);

const readFiniteNonNegativeInt = (value: number | null | undefined): number | null => {
    if (!isFiniteNumber(value)) {
        return null;
    }
    return Math.max(0, Math.floor(value));
};

const resolveCpuName = (cpu: CpuRaw): string => {
    return resolveHardwareDeviceDisplayName(cpu) ?? readNonEmptyString(cpu.model) ?? 'CPU';
};

const resolveCpuSocketIndex = (cpu: CpuRaw, fallbackIndex: number): number => {
    const socketId = typeof cpu.socketId === 'number' ? readFiniteNonNegativeInt(cpu.socketId) : null;
    return socketId ?? fallbackIndex;
};

const resolveCpuSocketsCount = (cpuArray: ReadonlyArray<CpuRaw>): number => {
    return cpuArray.length > 0 ? cpuArray.length : 1;
};

const extractCpuDevices = (hardware: HardwareSnapshot | HardwareData): CPUDevice[] => {
    const cpuArray = getCpuDevices(hardware);
    const normalizedMemoryData = hardware.memory ?? {};

    if (cpuArray.length > 0) {
        const sockets = resolveCpuSocketsCount(cpuArray);
        return cpuArray.map((cpu, index) => ({
            socketIndex: resolveCpuSocketIndex(cpu, index),
            name: resolveCpuName(cpu),
            sockets,
            cores: readFiniteNonNegativeInt(cpu.physicalCores) ?? 0,
            threads: readFiniteNonNegativeInt(cpu.logicalCores) ?? 0,
            data: formatCpuData(cpu, normalizedMemoryData)
        }));
    }

    return [];
};

const resolveGpuName = (gpu: HardwareGpuSnapshot): string => {
    return resolveHardwareDeviceDisplayName(gpu) ?? 'GPU';
};

const resolveGpuIndex = (gpu: HardwareGpuSnapshot, fallbackIndex: number): number => (isFiniteNumber(gpu.index) ? Math.max(0, Math.floor(gpu.index)) : fallbackIndex);

const extractGpuDevices = (hardware: HardwareSnapshot | HardwareData): GPUDevice[] => {
    const gpuArray = getGpuDevices(hardware);
    return gpuArray.map((gpu, index) => ({
        index: resolveGpuIndex(gpu, index),
        name: resolveGpuName(gpu),
        data: formatGpuData(gpu)
    }));
};

const isIgnoredNetworkInterfaceName = (name: string): boolean => {
    const normalized = name.trim().toLowerCase();
    return DEFAULT_IGNORED_NETWORK_PREFIXES.some((prefix) => normalized.startsWith(prefix));
};

const finiteMetric = (value: number | undefined): number => (isFiniteNumber(value) ? value : 0);

const formatNetworkData = (networkData: NetworkInterfaceRaw, speedData: NetworkSpeedEntry): NetworkDeviceData => {
    const download = finiteMetric(speedData.downloadMbps);
    const upload = finiteMetric(speedData.uploadMbps);
    const linkSpeed = finiteMetric(networkData.linkSpeedMbps);
    return {
        downloadMbps: Math.max(0, download),
        uploadMbps: Math.max(0, upload),
        linkSpeedMbps: Math.max(0, linkSpeed)
    };
};

const extractNetworkDevices = (hardware: HardwareSnapshot | HardwareData): NetworkDevice[] => {
    const networkSpeed = hardware.networkSpeed ?? null;
    const devices: NetworkDevice[] = [];
    for (const networkData of getNetworkInterfaces(hardware)) {
        const name = readNonEmptyString(networkData.name);
        const deviceId = readNonEmptyString(networkData.deviceId);
        if (!name || !deviceId || isIgnoredNetworkInterfaceName(name)) {
            continue;
        }
        devices.push({
            deviceId: deviceId,
            index: devices.length,
            name,
            data: formatNetworkData(networkData, resolveNetworkSpeedEntry(networkSpeed, name, deviceId) ?? {})
        });
    }
    return devices;
};

const formatCpuData = (cpuData: CpuRaw, memoryData: MemoryData): CPUDeviceData => {
    const utilization = finiteMetric(cpuData.usagePercent);
    const temperature = finiteMetric(cpuData.temperatureCelsius);
    const powerWatts = finiteMetric(cpuData.powerDrawWatts);
    const powerLimit = finiteMetric(cpuData.powerLimitWatts);
    const memoryValues = resolveMemoryValuesMb(memoryData);
    return {
        utilization,
        memoryUsedMb: memoryValues.usedMb,
        memoryTotalMb: memoryValues.totalMb,
        temperature,
        powerWatts: powerWatts,
        powerLimit: powerLimit
    };
};

const resolveGpuMemoryMb = (gpuData: HardwareGpuSnapshot): MemoryValues => {
    const usedMb = gpuData.memoryUsedMb;
    const totalMb = gpuData.memoryTotalMb;
    return {
        usedMb: isFiniteNumber(usedMb) && usedMb >= 0 ? usedMb : 0,
        totalMb: isFiniteNumber(totalMb) && totalMb > 0 ? totalMb : 0
    };
};

const formatGpuData = (gpuData: HardwareGpuSnapshot): GPUDeviceData => {
    if (gpuData.telemetryAvailable === false) {
        return {
            utilization: 0,
            memoryUsedMb: 0,
            memoryTotalMb: 0,
            powerWatts: 0,
            temperature: 0,
            powerLimit: 0,
            telemetryAvailable: false
        };
    }
    const utilization = finiteMetric(gpuData.utilization);
    const temperature = finiteMetric(gpuData.temperature);
    const memoryValues = resolveGpuMemoryMb(gpuData);
    const powerWatts = finiteMetric(gpuData.powerDrawWatts);
    const powerLimit = finiteMetric(gpuData.powerLimitWatts);
    return {
        utilization,
        memoryUsedMb: memoryValues.usedMb,
        memoryTotalMb: memoryValues.totalMb,
        powerWatts: powerWatts,
        temperature,
        powerLimit: powerLimit,
        telemetryAvailable: true
    };
};

const buildChartSeries = (points: ReadonlyArray<{ timestamp: number; [key: string]: number }>, metric: string, now: number, windowDurationMs: number, viewBox: number, normalizeMetricValue: MetricChartNormalizer): ChartPoint[] => {
    const windowStart = now - windowDurationMs;
    const normalized = points
        .map((point) => ({
            x: ((point.timestamp - windowStart) / windowDurationMs) * viewBox,
            y: viewBox - (clampNumber(normalizeMetricValue(point[metric] ?? 0, metric), 0, 100) / 100) * viewBox
        }))
        .filter((point) => point.x >= 0 && point.x <= viewBox);

    if (normalized.length === 0) {
        return [];
    }

    const first = normalized[0];
    if (!first) {
        throw new Error('Normalized chart series must have a first point when length > 0');
    }
    const last = normalized[normalized.length - 1];
    if (!last) {
        throw new Error('Normalized chart series must have a last point when length > 0');
    }
    const withBounds = [...normalized];
    if (first.x > 0) {
        withBounds.unshift({ x: 0, y: first.y });
    }
    if (last.x < viewBox) {
        withBounds.push({ x: viewBox, y: last.y });
    }

    return withBounds;
};

const createSmoothPath = (points: ReadonlyArray<ChartPoint>, viewBox: number): string => {
    if (points.length === 0) {
        return '';
    }
    const first = points[0];
    if (!first) {
        throw new Error('Smooth path requires at least one point');
    }
    const path = [`M 0 ${viewBox}`];
    path.push(`L ${first.x} ${first.y}`);

    for (let index = 0; index < points.length - 1; index += 1) {
        const current = points[index];
        if (!current) {
            throw new Error(`Smooth path point ${index} is missing`);
        }
        const next = points[index + 1];
        if (!next) {
            throw new Error(`Smooth path point ${index + 1} is missing`);
        }
        const delta = next.x - current.x;
        path.push(`C ${current.x + delta / 3},${current.y} ${current.x + (2 * delta) / 3},${next.y} ${next.x},${next.y}`);
    }

    const last = points[points.length - 1];
    if (!last) {
        throw new Error('Smooth path requires a last point when length > 0');
    }
    path.push(`L ${last.x} ${viewBox}`, 'Z');
    return path.join(' ');
};

const createSmoothLine = (points: ReadonlyArray<ChartPoint>): string => {
    if (points.length === 0) {
        return '';
    }

    const first = points[0];
    if (!first) {
        throw new Error('Smooth line requires at least one point');
    }
    const path = [`M ${first.x} ${first.y}`];

    for (let index = 0; index < points.length - 1; index += 1) {
        const current = points[index];
        if (!current) {
            throw new Error(`Smooth line point ${index} is missing`);
        }
        const next = points[index + 1];
        if (!next) {
            throw new Error(`Smooth line point ${index + 1} is missing`);
        }
        const delta = next.x - current.x;
        path.push(`C ${current.x + delta / 3},${current.y} ${current.x + (2 * delta) / 3},${next.y} ${next.x},${next.y}`);
    }

    return path.join(' ');
};

export { readNonEmptyString, readFiniteNonNegativeInt, resolveCpuName, resolveCpuSocketIndex, resolveCpuSocketsCount, resolveGpuName, resolveGpuIndex, extractCpuDevices, extractGpuDevices, extractNetworkDevices, formatCpuData, formatGpuData, formatNetworkData, buildChartSeries, createSmoothPath, createSmoothLine };
