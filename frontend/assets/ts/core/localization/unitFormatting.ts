/* SoAI - Shared localization unit formatting [frontend/assets/ts/core/localization/unitFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocalizationSnapshot } from '@core/localization/runtime.ts';
import { formatInvariantNumber } from '@core/localization/numberFormatting.ts';

const BYTES_PER_KIB = 1024;
const BYTE_UNITS: readonly string[] = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

const celsiusToFahrenheit = (value: number): number => value * 1.8 + 32;

const fahrenheitToCelsius = (value: number): number => (value - 32) / 1.8;

const kilometersPerHourToMilesPerHour = (value: number): number => value / 1.609344;

const milesPerHourToKilometersPerHour = (value: number): number => value * 1.609344;

const wattsToBtuPerHour = (value: number): number => value * 3.412142;

const formatByteSize = (bytes: number, fractionDigits: number = 1): string => {
    if (!Number.isFinite(bytes)) {
        return `0 ${BYTE_UNITS[0]}`;
    }
    let value = Math.abs(bytes);
    let unitIndex = 0;
    while (value >= BYTES_PER_KIB && unitIndex < BYTE_UNITS.length - 1) {
        value /= BYTES_PER_KIB;
        unitIndex += 1;
    }
    const signedValue = bytes < 0 ? -value : value;
    const digits = unitIndex === 0 ? 0 : fractionDigits;
    return `${formatInvariantNumber(signedValue, { maximumFractionDigits: digits })} ${BYTE_UNITS[unitIndex]}`;
};

const formatTemperature = (celsius: number, fractionDigits: number = 1): string => {
    const snapshot = getLocalizationSnapshot();
    if (snapshot.measurementUnits === 'imperial') {
        return `${formatInvariantNumber(celsiusToFahrenheit(celsius), { maximumFractionDigits: fractionDigits })} °F`;
    }
    return `${formatInvariantNumber(celsius, { maximumFractionDigits: fractionDigits })} °C`;
};

const formatWindSpeed = (kilometersPerHour: number, fractionDigits: number = 1): string => {
    const snapshot = getLocalizationSnapshot();
    if (snapshot.measurementUnits === 'imperial') {
        return `${formatInvariantNumber(kilometersPerHourToMilesPerHour(kilometersPerHour), { maximumFractionDigits: fractionDigits })} mph`;
    }
    return `${formatInvariantNumber(kilometersPerHour, { maximumFractionDigits: fractionDigits })} km/h`;
};

const formatPower = (watts: number, fractionDigits: number = 1): string => {
    const snapshot = getLocalizationSnapshot();
    if (snapshot.measurementUnits === 'imperial') {
        return `${formatInvariantNumber(wattsToBtuPerHour(watts), { maximumFractionDigits: fractionDigits })} BTU/h`;
    }
    return `${formatInvariantNumber(watts, { maximumFractionDigits: fractionDigits })} W`;
};

const formatNetworkSpeedMbps = (megabitsPerSecond: number): string => {
    const absValue = Math.abs(megabitsPerSecond);
    if (absValue >= 1000000) {
        return `${formatInvariantNumber(megabitsPerSecond / 1000000, { maximumFractionDigits: 1 })} Tbps`;
    }
    if (absValue >= 1000) {
        return `${formatInvariantNumber(megabitsPerSecond / 1000, { maximumFractionDigits: 1 })} Gbps`;
    }
    return `${formatInvariantNumber(megabitsPerSecond, { maximumFractionDigits: 1 })} Mbps`;
};

export { celsiusToFahrenheit, fahrenheitToCelsius, formatByteSize, formatNetworkSpeedMbps, formatPower, formatTemperature, formatWindSpeed, kilometersPerHourToMilesPerHour, milesPerHourToKilometersPerHour, wattsToBtuPerHour };
