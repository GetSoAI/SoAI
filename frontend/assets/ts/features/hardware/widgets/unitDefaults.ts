/* SoAI - Hardware feature unit defaults [frontend/assets/ts/features/hardware/widgets/unitDefaults.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocalizationSnapshot, type ResolvedMeasurementUnits } from '@core/localization/public.ts';
import type { UnitConfig } from '@features/hardware/widgets/contracts.ts';

type StandardMemoryMetric = 'ram' | 'vram';

const resolveTemperatureUnit = (measurementUnits: ResolvedMeasurementUnits): string => (measurementUnits === 'imperial' ? 'F' : 'C');

const resolvePowerUnit = (measurementUnits: ResolvedMeasurementUnits): string => (measurementUnits === 'imperial' ? 'BTU' : 'W');

const createStandardHardwareUnitConfig = (memoryMetric: StandardMemoryMetric): Record<string, UnitConfig> => {
    const measurementUnits = getLocalizationSnapshot().measurementUnits;
    return {
        [memoryMetric]: { current: 'GB', alternatives: ['GB', 'MB'] },
        power: { current: resolvePowerUnit(measurementUnits), alternatives: ['W', 'BTU'] },
        temperature: { current: resolveTemperatureUnit(measurementUnits), alternatives: ['C', 'F'] }
    };
};

export { createStandardHardwareUnitConfig };
