/* SoAI - Wizard AI setup hardware facts [frontend/assets/ts/pages/wizard/services/aisetup/facts/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareGpuSnapshot, HardwareSnapshotResponse } from '@core/api/contracts/hardwareContractTypes.ts';
import { detectHardwareBrand, type HardwareBrand } from '@core/hardwareBrands.ts';
import { toLowerCase } from '@core/normalize.ts';

const MEBIBYTE = 1024 * 1024;

interface HardwareGpuFacts {
    vramBytes: number | null;
    unifiedMemory: boolean;
    brand: HardwareBrand;
}

interface HardwareFacts {
    systemRamBytes: number | null;
    gpus: HardwareGpuFacts[];
}

const readPositive = (value: number | undefined): number | null => (value !== undefined && Number.isFinite(value) && value > 0 ? value : null);

const readGpuFacts = (gpu: HardwareGpuSnapshot): HardwareGpuFacts => {
    const memoryTotalMb = readPositive(gpu.memoryTotalMb);
    return {
        vramBytes: readPositive(gpu.memoryTotalBytes) ?? (memoryTotalMb === null ? null : memoryTotalMb * MEBIBYTE),
        unifiedMemory: toLowerCase(gpu.vendor) === 'apple' || toLowerCase(gpu.type) === 'apple',
        brand: detectHardwareBrand([gpu.vendor, gpu.type, gpu.name].filter((value) => value !== undefined).join(' '))
    };
};

const readHardwareFacts = (snapshot: HardwareSnapshotResponse | null): HardwareFacts => ({
    systemRamBytes: readPositive(snapshot?.memory?.totalBytes),
    gpus: (snapshot?.gpu?.gpus ?? []).filter((gpu) => gpu.computeCapable !== false).map(readGpuFacts)
});

const hardwareFactsRequireRetry = (snapshot: HardwareSnapshotResponse | null): boolean => {
    if (snapshot === null || snapshot.gpu === undefined) return true;
    const memoryStatus = snapshot.componentStatus?.['memory']?.status;
    if (snapshot.memory === undefined && memoryStatus !== 'unavailable') return true;
    if (memoryStatus === 'stale' || memoryStatus === 'disconnected' || memoryStatus === 'partial' || (memoryStatus === 'unavailable' && readPositive(snapshot.memory?.totalBytes) !== null)) return true;
    const gpuStatus = snapshot.componentStatus?.['gpu']?.status;
    if (gpuStatus === 'stale' || gpuStatus === 'disconnected' || gpuStatus === 'partial' || (gpuStatus === 'unavailable' && snapshot.gpu.gpus.length > 0)) return true;
    const sources = snapshot.gpu.inventorySources;
    const nvidiaOptional =
        sources?.['cim']?.state === 'observed' &&
        snapshot.gpu.gpus.every((gpu) => {
            const vendors = [gpu.type, gpu.vendor].filter((vendor): vendor is string => vendor !== undefined).map((vendor) => toLowerCase(vendor));
            return vendors.length > 0 && vendors.every((vendor) => vendor === vendors[0] && (vendor === 'amd' || vendor === 'intel'));
        });
    return Object.entries(sources ?? {}).some(([name, source]) => {
        if (name === 'nvidia' && nvidiaOptional && (source.state === 'query_failed' || source.state === 'runtime_unavailable')) return false;
        return source.state !== 'observed' && source.state !== 'unknown';
    });
};

export { hardwareFactsRequireRetry, readHardwareFacts };
export type { HardwareFacts, HardwareGpuFacts };
