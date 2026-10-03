/* SoAI - Wizard AI setup hardware facts [frontend/assets/ts/pages/wizard/services/aisetup/facts/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareGpuSnapshot, HardwareSnapshotResponse } from '@core/api/contracts/hardwareContractTypes.ts';
import { toLowerCase } from '@core/normalize.ts';

const MEBIBYTE = 1024 * 1024;

interface HardwareGpuFacts {
    vramBytes: number | null;
    unifiedMemory: boolean;
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
        unifiedMemory: toLowerCase(gpu.vendor) === 'apple' || toLowerCase(gpu.type) === 'apple'
    };
};

const readHardwareFacts = (snapshot: HardwareSnapshotResponse | null): HardwareFacts => ({
    systemRamBytes: readPositive(snapshot?.memory?.totalBytes),
    gpus: (snapshot?.gpu?.gpus ?? []).filter((gpu) => gpu.computeCapable !== false).map(readGpuFacts)
});

export { readHardwareFacts };
export type { HardwareFacts, HardwareGpuFacts };
