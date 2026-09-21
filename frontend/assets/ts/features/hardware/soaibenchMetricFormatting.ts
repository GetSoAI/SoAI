/* SoAI - Hardware feature SoAI Bench metric formatting [frontend/assets/ts/features/hardware/soaibenchMetricFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatPositiveEpochMsMinuteWithFallback } from '@core/primitives/dateTime.ts';
import { formatCompactDurationFromMs } from '@core/primitives/duration.ts';
import { formatHardwareNumber } from '@features/hardware/Formatters.ts';
import { formatUnexpectedSoAIBenchIdentifierLabel } from '@features/hardware/soaibenchLabels.ts';

interface SoAIBenchCertificationInput {
    profile: string;
    benchmarkMode: string;
    leaderboardEligible: boolean;
    leaderboardRejectionReason: string | null;
    scoreVariancePercent: number | null;
    legacy: boolean;
}

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

const formatSoAIBenchStartedAt = (value: number | null): string => {
    return formatPositiveEpochMsMinuteWithFallback(value, getSoAIBenchNotAvailableLabel());
};

const formatSoAIBenchTemperature = (value: number | null): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : `${formatHardwareNumber(value, 1)}\u00b0C`;
};

const formatSoAIBenchPercentValue = (value: number | null, decimals: number): string => {
    return value === null ? getSoAIBenchNotAvailableLabel() : `${formatHardwareNumber(value, decimals)}%`;
};

const formatSoAIBenchSignedPercentValue = (value: number | null, decimals: number): string => {
    if (value === null) return getSoAIBenchNotAvailableLabel();
    const prefix = value > 0 ? '+' : '';
    return `${prefix}${formatHardwareNumber(value, decimals)}%`;
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

const formatCertificationVariance = (value: number | null): string => {
    return value === null ? '' : ` (${i18n.t('hardware.modals.soaibenchHistory.certification.varianceSuffix', { variance: formatHardwareNumber(value, 1) })})`;
};

const formatSoAIBenchCertification = (input: SoAIBenchCertificationInput): string => {
    if (input.profile !== 'standard') {
        return getSoAIBenchNotAvailableLabel();
    }
    if (input.legacy) {
        return `${i18n.t('hardware.modals.soaibenchHistory.certification.legacy')}${formatCertificationVariance(input.scoreVariancePercent)}`;
    }
    if (input.benchmarkMode !== 'certified') {
        return i18n.t('hardware.modals.soaibenchHistory.certification.quick');
    }
    if (input.leaderboardEligible) {
        return `${i18n.t('hardware.modals.soaibenchHistory.certification.certified')}${formatCertificationVariance(input.scoreVariancePercent)}`;
    }
    const reason = formatUnexpectedSoAIBenchIdentifierLabel(input.leaderboardRejectionReason);
    return `${i18n.t('hardware.modals.soaibenchHistory.certification.ineligible', { reason })}${formatCertificationVariance(input.scoreVariancePercent)}`;
};

export { formatSoAIBenchCertification, formatSoAIBenchDuration, formatSoAIBenchMetric, formatSoAIBenchPercentValue, formatSoAIBenchPowerPair, formatSoAIBenchScore, formatSoAIBenchSignedPercentValue, formatSoAIBenchStartedAt, formatSoAIBenchTemperature, formatSoAIBenchThroughputValue, getSoAIBenchNotAvailableLabel };
export type { SoAIBenchCertificationInput };
