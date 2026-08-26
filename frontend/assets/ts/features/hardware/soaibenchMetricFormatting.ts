/* SoAI - Hardware feature SoAI Bench metric formatting [frontend/assets/ts/features/hardware/soaibenchMetricFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatCompactDurationFromMs } from '@core/primitives/duration.ts';
import { formatHardwareNumber } from '@features/hardware/Formatters.ts';

const getSoAIBenchNotAvailableLabel = (): string => i18n.t('common.notAvailableShort');

const formatSoAIBenchScore = (value: number | null): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : formatHardwareNumber(value, 0);
};

const formatSoAIBenchMetric = (value: number | null, decimals: number): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : formatHardwareNumber(value, decimals);
};

const formatSoAIBenchDuration = (value: number | null): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : formatCompactDurationFromMs(value);
};

const formatSoAIBenchTemperature = (value: number | null): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : `${formatHardwareNumber(value, 1)}\u00b0C`;
};

const formatSoAIBenchPercentValue = (value: number | null, decimals: number): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : `${formatHardwareNumber(value, decimals)}%`;
};

const formatSoAIBenchThroughputValue = (value: number | null, unit: string): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : `${formatHardwareNumber(value, 1)} ${unit}`;
};

const formatSoAIBenchPowerPair = (avgValue: number | null, maxValue: number | null): string => {
    if (avgValue === null && maxValue === null) {
        return getSoAIBenchNotAvailableLabel();
    }
    const avgText = avgValue === null ? getSoAIBenchNotAvailableLabel() : formatHardwareNumber(avgValue, 1);
    const maxText = maxValue === null ? getSoAIBenchNotAvailableLabel() : formatHardwareNumber(maxValue, 1);
    return `${avgText} / ${maxText} W`;
};

export { formatSoAIBenchDuration, formatSoAIBenchMetric, formatSoAIBenchPercentValue, formatSoAIBenchPowerPair, formatSoAIBenchScore, formatSoAIBenchTemperature, formatSoAIBenchThroughputValue, getSoAIBenchNotAvailableLabel };
