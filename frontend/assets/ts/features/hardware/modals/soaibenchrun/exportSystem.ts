/* SoAI - SoAIBench export system projection [frontend/assets/ts/features/hardware/modals/soaibenchrun/exportSystem.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

interface SoAIBenchExportSystem {
    cpuName: string | null;
    ramGb: number | null;
    soaiVersion: string | null;
}

const projectSoAIBenchExportSystem = (raw: JsonObject): SoAIBenchExportSystem => {
    const environmentValue = raw['environment'];
    const environment = isJsonObject(environmentValue) ? environmentValue : {};
    const cpuValue = environment['cpu_name'];
    const ramValue = environment['system_ram_gb'];
    const versionValue = environment['soai_version'];
    return {
        cpuName: typeof cpuValue === 'string' && cpuValue.trim() ? cpuValue.trim() : null,
        ramGb: typeof ramValue === 'number' && Number.isFinite(ramValue) && ramValue > 0 ? ramValue : null,
        soaiVersion: typeof versionValue === 'string' && versionValue.trim() ? versionValue.trim() : null
    };
};

export { projectSoAIBenchExportSystem };
export type { SoAIBenchExportSystem };
