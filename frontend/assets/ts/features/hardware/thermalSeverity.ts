/* SoAI - Hardware feature thermal severity [frontend/assets/ts/features/hardware/thermalSeverity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';

const TEMPERATURE_WARNING_CELSIUS = 80;
const TEMPERATURE_CRITICAL_CELSIUS = 90;
const TEMPERATURE_MAX_SCALE_CELSIUS = 100;

type TemperatureSeverity = 'normal' | 'warning' | 'critical';

const resolveTemperatureSeverity = (temperatureCelsius: number | null | undefined): TemperatureSeverity => {
    if (!isFiniteNumber(temperatureCelsius)) {
        return 'normal';
    }
    if (temperatureCelsius >= TEMPERATURE_CRITICAL_CELSIUS) {
        return 'critical';
    }
    if (temperatureCelsius > TEMPERATURE_WARNING_CELSIUS) {
        return 'warning';
    }
    return 'normal';
};

export { TEMPERATURE_CRITICAL_CELSIUS, TEMPERATURE_MAX_SCALE_CELSIUS, TEMPERATURE_WARNING_CELSIUS, resolveTemperatureSeverity };
export type { TemperatureSeverity };
