/* SoAI - Hardware feature formatters [frontend/assets/ts/features/hardware/Formatters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatBytes } from '@core/primitives/byteSize.ts';
import { formatElapsedRuntimeFromStartMs } from '@core/primitives/duration.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import { formatInvariantNumber, formatNetworkSpeedMbps, wattsToBtuPerHour } from '@core/localization/public.ts';
import { readNumberCoercedFiniteNumberValue } from '@core/types/numberCoercionReaders.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';

const PROCESS_MEMORY_ERROR = 'Process memory must be a non-negative number';

const safeNumberFormat = (value: number, formatter: (numeric: number) => string): string => {
    const numeric = readNumberCoercedFiniteNumberValue(value, 'Numeric value required for hardware formatter');
    return formatter(numeric);
};

const formatHardwareNumber = (value: number, decimals: number = 1): string => {
    if (!isFiniteNumber(value)) return '0';
    return formatInvariantNumber(value, { maximumFractionDigits: value % 1 === 0 ? 0 : decimals });
};

const formatGigabytes = (value: number): string => {
    return isFiniteNumber(value) ? `${formatInvariantNumber(value, { maximumFractionDigits: 2 })} GB` : '—';
};

const formatBytesValue = (value: number): string => {
    const numeric = readNumberCoercedFiniteNumberValue(value, 'Byte value must be a finite number');
    return formatBytes(numeric);
};

const formatProcessCpu = (value: number): string => {
    const numeric = value || 0;
    return formatPercent(numeric, numeric >= 100 ? 0 : 1);
};

const formatProcessMemory = (megabytes: number): string => {
    const numeric = readNumberCoercedFiniteNumberValue(megabytes, PROCESS_MEMORY_ERROR);
    if (numeric < 0) {
        throw new Error(PROCESS_MEMORY_ERROR);
    }
    if (numeric >= 1024) {
        return `${formatInvariantNumber(numeric / 1024, { maximumFractionDigits: 1 })} GB`;
    }
    return `${formatInvariantNumber(numeric, { maximumFractionDigits: 0 })} MB`;
};

const formatProcessRuntime = (createTime: number): string => formatElapsedRuntimeFromStartMs(createTime, serverEpochMs());

const formatMemoryUsage = (usedMb: number, totalMb: number, unit: string): string => {
    const usedValue = unit === 'GB' ? usedMb / 1024 : usedMb;
    const totalValue = unit === 'GB' ? totalMb / 1024 : totalMb;
    return `${formatHardwareNumber(usedValue)}/${formatHardwareNumber(totalValue)}${unit}`;
};

const formatPowerWatts = (watts: number, unit: string): string => {
    const value = unit === 'BTU' ? wattsToBtuPerHour(watts) : watts;
    return `${formatInvariantNumber(Math.round(value), { maximumFractionDigits: 0 })}${unit}`;
};

const formatSpeedValue = (value: number): string => {
    const numeric = Number(value);
    if (!isFiniteNumber(numeric) || numeric < 0) {
        return '0 bps';
    }
    if (numeric >= 1_000_000) {
        return formatNetworkSpeedMbps(numeric);
    }
    if (numeric >= 1000) {
        return formatNetworkSpeedMbps(numeric);
    }
    if (numeric > 0 && numeric < 1 && numeric >= 0.001) {
        return `${Math.round(numeric * 1000)} Kbps`;
    }
    if (numeric > 0 && numeric < 0.001) {
        return `${Math.round(numeric * 1_000_000)} bps`;
    }
    if (numeric === 0) {
        return '0 bps';
    }
    return `${formatInvariantNumber(numeric, { maximumFractionDigits: numeric >= 10 ? 1 : 2 })} Mbps`;
};

const formatRateValue = (value: number): string => formatSpeedValue(value);

const netmaskToCidr = (netmask: string): number | null => {
    if (!netmask) {
        return null;
    }
    const parts = netmask.split('.');
    if (parts.length !== 4) {
        return null;
    }
    let cidr = 0;
    for (const part of parts) {
        const numeric = parseInt(part, 10);
        if (!isFiniteNumber(numeric) || numeric < 0 || numeric > 255) {
            return null;
        }
        const bits = (numeric >>> 0)
            .toString(2)
            .split('')
            .reduce((sum, bit) => sum + (bit === '1' ? 1 : 0), 0);
        cidr += bits;
    }
    return cidr;
};

interface HardwareFormatters {
    safeNumberFormat: typeof safeNumberFormat;
    formatHardwareNumber: typeof formatHardwareNumber;
    formatGigabytes: typeof formatGigabytes;
    formatBytesValue: typeof formatBytesValue;
    formatRateValue: typeof formatRateValue;
    formatProcessCpu: typeof formatProcessCpu;
    formatProcessMemory: typeof formatProcessMemory;
    formatProcessRuntime: typeof formatProcessRuntime;
    formatMemoryUsage: typeof formatMemoryUsage;
    formatPowerWatts: typeof formatPowerWatts;
    formatSpeedValue: typeof formatSpeedValue;
    netmaskToCidr: typeof netmaskToCidr;
}

const hardwareFormatters: Readonly<HardwareFormatters> = Object.freeze({
    safeNumberFormat,
    formatHardwareNumber,
    formatGigabytes,
    formatBytesValue,
    formatRateValue,
    formatProcessCpu,
    formatProcessMemory,
    formatProcessRuntime,
    formatMemoryUsage,
    formatPowerWatts,
    formatSpeedValue,
    netmaskToCidr
});

export { hardwareFormatters, safeNumberFormat, formatHardwareNumber, formatGigabytes, formatBytesValue, formatRateValue, formatProcessCpu, formatProcessMemory, formatProcessRuntime, formatMemoryUsage, formatPowerWatts, formatSpeedValue, netmaskToCidr };
export type { HardwareFormatters };
