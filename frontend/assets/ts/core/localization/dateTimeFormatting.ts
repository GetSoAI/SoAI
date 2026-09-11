/* SoAI - Shared localization date time formatting [frontend/assets/ts/core/localization/dateTimeFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocalizationSnapshot } from '@core/localization/runtime.ts';

const UTC_LABEL = ' UTC';
const UNLABELED_UTC_LOG_TIMESTAMP_PATTERN = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/;

const formatUtcLogTimestamp = (timestamp: string): string => {
    if (!UNLABELED_UTC_LOG_TIMESTAMP_PATTERN.test(timestamp)) {
        return timestamp;
    }
    return timestamp + UTC_LABEL;
};

const applyClockPreference = (options: Intl.DateTimeFormatOptions): Intl.DateTimeFormatOptions => {
    const snapshot = getLocalizationSnapshot();
    if (options.hour === undefined) {
        return { ...options };
    }
    return { ...options, hour12: snapshot.hour12 };
};

const applyDateOrderPreference = (options: Intl.DateTimeFormatOptions): Intl.DateTimeFormatOptions => {
    const snapshot = getLocalizationSnapshot();
    if (snapshot.dateOrder === 'locale') {
        return { ...options };
    }
    const base = { ...options };
    if (base.year === undefined && base.month === undefined && base.day === undefined) {
        return base;
    }
    if (snapshot.dateOrder === 'iso') {
        base.year = 'numeric';
        base.month = '2-digit';
        base.day = '2-digit';
        return base;
    }
    base.year = base.year ?? 'numeric';
    base.month = base.month ?? '2-digit';
    base.day = base.day ?? '2-digit';
    return base;
};

const resolveDateFormattingLocale = (): string => {
    const snapshot = getLocalizationSnapshot();
    if (snapshot.dateOrder === 'us') {
        return 'en-US';
    }
    if (snapshot.dateOrder === 'eu') {
        return 'en-GB';
    }
    if (snapshot.dateOrder === 'iso') {
        return 'sv-SE';
    }
    return snapshot.locale;
};

const formatLocalizedDate = (date: Date, options: Intl.DateTimeFormatOptions = {}): string => {
    const resolvedOptions = applyClockPreference(applyDateOrderPreference(options));
    return new Intl.DateTimeFormat(resolveDateFormattingLocale(), resolvedOptions).format(date);
};

const formatLocalizedDateParts = (date: Date, options: Intl.DateTimeFormatOptions = {}): Intl.DateTimeFormatPart[] => {
    const resolvedOptions = applyClockPreference(applyDateOrderPreference(options));
    return new Intl.DateTimeFormat(resolveDateFormattingLocale(), resolvedOptions).formatToParts(date);
};

const formatLocalizedRelativeTime = (value: number, unit: Intl.RelativeTimeFormatUnit): string => {
    return new Intl.RelativeTimeFormat(getLocalizationSnapshot().locale, { numeric: 'auto' }).format(value, unit);
};

export { formatLocalizedDate, formatLocalizedDateParts, formatLocalizedRelativeTime, formatUtcLogTimestamp };
