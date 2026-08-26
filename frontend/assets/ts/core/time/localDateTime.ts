/* SoAI - Locale-aware local date and time formatting [frontend/assets/ts/core/time/localDateTime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface LocalDateTimeParts {
    year: number;
    month: number;
    day: number;
    hour: number;
    minute: number;
}

const createUtcDate = (year: number, monthIndex: number, day: number, hour: number, minute: number): Date => {
    const date = new Date(0);
    date.setUTCFullYear(year, monthIndex, day);
    date.setUTCHours(hour, minute, 0, 0);
    return date;
};

const daysInMonth = (year: number, month: number): number => createUtcDate(year, month, 0, 0, 0).getUTCDate();

const parseLocalDateTimeParts = (value: string): LocalDateTimeParts | null => {
    const raw = value.trim();
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(raw);
    if (!match) {
        return null;
    }
    const year = Number(match[1] || '');
    const month = Number(match[2] || '');
    const day = Number(match[3] || '');
    const hour = Number(match[4] || '');
    const minute = Number(match[5] || '');
    if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day) || !Number.isInteger(hour) || !Number.isInteger(minute)) {
        return null;
    }
    if (month < 1 || month > 12) return null;
    if (day < 1 || day > daysInMonth(year, month)) return null;
    if (hour < 0 || hour > 23) return null;
    if (minute < 0 || minute > 59) return null;
    return { year, month, day, hour, minute };
};

const parseLocalDateTimeToUtcDate = (value: string): Date | null => {
    const parts = parseLocalDateTimeParts(value);
    if (!parts) {
        return null;
    }
    const monthIndex = parts.month - 1;
    const date = createUtcDate(parts.year, monthIndex, parts.day, parts.hour, parts.minute);
    if (Number.isNaN(date.getTime())) {
        return null;
    }
    if (date.getUTCFullYear() !== parts.year || date.getUTCMonth() !== monthIndex || date.getUTCDate() !== parts.day || date.getUTCHours() !== parts.hour || date.getUTCMinutes() !== parts.minute) {
        return null;
    }
    return date;
};

export { parseLocalDateTimeParts, parseLocalDateTimeToUtcDate };
export type { LocalDateTimeParts };
