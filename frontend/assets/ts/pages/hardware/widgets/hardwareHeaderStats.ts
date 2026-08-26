/* SoAI - Hardware page header stats [frontend/assets/ts/pages/hardware/widgets/hardwareHeaderStats.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareCapabilitiesResponse, HardwareSnapshotResponse } from '@core/api/contracts/hardwareContracts.ts';
import { formatCompactDurationFromMs } from '@core/primitives/duration.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { formatGigabytes, getCpuDevices } from '@features/hardware/public.ts';
import type { MetricsData } from '@pages/hardware/types.ts';

interface HardwareHeaderStatsInput {
    snapshot: HardwareSnapshotResponse;
    capabilities: HardwareCapabilitiesResponse;
    currentMetrics: MetricsData | null;
    processCount: number;
}

interface HardwareHeaderStatsOutput {
    processes: string;
    cpu: string;
    totalRam: string;
    totalVram: string;
    totalMemory: string;
    platform: string;
    systemUptime: string;
    totalUptime: string;
}

const formatHardwareUptime = (uptimeMs: number | undefined): string => {
    return isFiniteNumber(uptimeMs) && uptimeMs >= 0 ? formatCompactDurationFromMs(uptimeMs) : '—';
};

const formatHardwareSystemUptime = (snapshot: HardwareSnapshotResponse): string => {
    return formatHardwareUptime(snapshot.uptime?.uptimeMs);
};

export const formatHardwareTotalUptime = (metrics: MetricsData | null): string => {
    return formatHardwareUptime(metrics?.genesis?.uptimeMs);
};

export const resolveHardwarePlatformLabel = (capabilities: HardwareCapabilitiesResponse): string => {
    const capabilitiesValue = capabilities.platform;
    if (!capabilitiesValue?.trim()) {
        return '—';
    }
    const resolved = capabilitiesValue.trim();
    return resolved.charAt(0).toUpperCase() + resolved.slice(1);
};

export const buildHardwareHeaderStats = (input: HardwareHeaderStatsInput): HardwareHeaderStatsOutput => {
    const summary = input.snapshot.summary;
    const capabilities = input.capabilities;
    const cpus = getCpuDevices(input.snapshot);
    const avgCpu = cpus.length ? cpus.reduce((acc, cpu) => acc + (Number(cpu.usagePercent) || 0), 0) / cpus.length : 0;

    const totalRamRaw = summary.totalSystemRamGb ?? capabilities.systemRamGb;
    const totalVramRaw = summary.totalVramGb ?? capabilities.totalVramGb;
    const totalMemoryRaw = summary.totalSystemMemoryGb ?? capabilities.totalSystemMemoryGb;
    const totalRam = Number(totalRamRaw);
    const totalVram = Number(totalVramRaw);
    const totalMemory = Number(totalMemoryRaw);
    const totalRamLabel = Number.isFinite(totalRam) && totalRam > 0 ? formatGigabytes(totalRam) : '—';
    const totalVramLabel = Number.isFinite(totalVram) && totalVram >= 0 ? formatGigabytes(totalVram) : '—';
    const totalMemoryLabel = Number.isFinite(totalMemory) && totalMemory > 0 ? formatGigabytes(totalMemory) : '—';

    return {
        processes: String(input.processCount),
        cpu: avgCpu > 0 ? `${Math.round(avgCpu)}%` : '—',
        totalRam: totalRamLabel,
        totalVram: totalVramLabel,
        totalMemory: totalMemoryLabel,
        platform: resolveHardwarePlatformLabel(capabilities),
        systemUptime: formatHardwareSystemUptime(input.snapshot),
        totalUptime: formatHardwareTotalUptime(input.currentMetrics)
    };
};
