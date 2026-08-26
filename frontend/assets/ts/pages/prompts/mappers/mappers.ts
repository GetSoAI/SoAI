/* SoAI - Prompts page mapping [frontend/assets/ts/pages/prompts/mappers/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import { formatDateTimeSecond } from '@core/primitives/dateTime.ts';
import { resolveAlphabeticGroupKey } from '@core/primitives/grouping.ts';
import { sanitizeDownloadFilename } from '@core/primitives/download.ts';
import { daysToMs, hoursToMs, msToMinutes } from '@core/time/durations.ts';
import { resolveLocalCalendarBucket, startOfDay } from '@core/time/localCalendar.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isArray, isFiniteNumber, isNullOrUndefined } from '@core/typeGuards.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import type { ColorToolkitInterface, PromptGroup } from '@pages/prompts/contracts/contracts.ts';

const PROMPT_RELATIVE_TIMESTAMP_LIMIT_MS = hoursToMs(2);

interface DateBoundaries {
    today: number;
    yesterday: number;
    weekStart: number;
    monthStart: number;
}

const DAY_IN_MS = daysToMs(1);

const resolveDateBoundaries = (now: Date): DateBoundaries => {
    const today = startOfDay(now).getTime();
    const yesterday = today - DAY_IN_MS;
    const weekStartDate = new Date(today);
    weekStartDate.setDate(weekStartDate.getDate() - weekStartDate.getDay());

    return {
        today,
        yesterday,
        weekStart: weekStartDate.getTime(),
        monthStart: new Date(now.getFullYear(), now.getMonth(), 1).getTime()
    };
};

const resolveDateGroupKey = (modifiedAtMs: number, boundaries: DateBoundaries): string => {
    if (!isFiniteNumber(modifiedAtMs)) {
        return 'older';
    }
    const dayEpoch = startOfDay(new Date(modifiedAtMs)).getTime();
    const { today, yesterday, weekStart, monthStart } = boundaries;
    if (dayEpoch >= today) {
        return 'today';
    }
    if (dayEpoch === yesterday) {
        return 'yesterday';
    }
    if (dayEpoch >= weekStart) {
        return 'thisWeek';
    }
    if (dayEpoch >= monthStart) {
        return 'thisMonth';
    }
    return 'older';
};

const resolveDateGroupHeading = (groupKey: string): string => {
    if (groupKey === 'today') return i18n.t('prompts.dateGroups.today');
    if (groupKey === 'yesterday') return i18n.t('prompts.dateGroups.yesterday');
    if (groupKey === 'thisWeek') return i18n.t('prompts.dateGroups.thisWeek');
    if (groupKey === 'thisMonth') return i18n.t('prompts.dateGroups.thisMonth');
    return i18n.t('prompts.dateGroups.older');
};

export const comparePromptNames = (left: string | null | undefined, right: string | null | undefined): number => {
    const firstValue = left ?? '';
    const secondValue = right ?? '';
    return firstValue.localeCompare(secondValue, getCurrentLocale(), { sensitivity: 'base', numeric: true });
};

export const mapPromptsByDate = (prompts: PromptRecord[], now: Date, dateGroups: ReadonlyArray<string>): PromptGroup[] => {
    if (!isArray(prompts) || prompts.length === 0) {
        return [];
    }
    const boundaries = resolveDateBoundaries(now);
    const buckets = new Map<string, PromptGroup>(
        dateGroups.map((key: string) => [
            key,
            {
                heading: resolveDateGroupHeading(key),
                prompts: []
            }
        ])
    );

    for (const prompt of prompts) {
        const bucketKey = resolveDateGroupKey(prompt.modifiedAtMs, boundaries);
        const bucket = buckets.get(bucketKey);
        if (bucket) {
            bucket.prompts.push(prompt);
        }
    }

    return dateGroups.map((key: string) => buckets.get(key)).filter((bucket): bucket is PromptGroup => bucket !== undefined && bucket.prompts.length > 0);
};

export const mapPromptsByName = (prompts: PromptRecord[]): PromptGroup[] => {
    if (!isArray(prompts) || prompts.length === 0) {
        return [];
    }
    const buckets = new Map<string, PromptRecord[]>();

    for (const prompt of prompts) {
        const key = resolveAlphabeticGroupKey(prompt.name);
        const bucket = buckets.get(key);
        if (bucket) {
            bucket.push(prompt);
        } else {
            buckets.set(key, [prompt]);
        }
    }

    return Array.from(buckets.keys())
        .sort(comparePromptNames)
        .map((key: string) => {
            const promptsForKey = buckets.get(key);
            if (!isArray(promptsForKey)) {
                throw new TypeError(`Bucket for key ${key} must contain an array`);
            }
            return { heading: key, prompts: promptsForKey };
        })
        .filter((bucket: PromptGroup) => bucket.prompts.length > 0);
};

export const mapPromptsByColor = (prompts: PromptRecord[], colorToolkit: ColorToolkitInterface): PromptGroup[] => {
    if (!isArray(prompts) || prompts.length === 0) {
        return [];
    }
    const buckets = new Map<string, PromptRecord[]>();

    for (const prompt of prompts) {
        const normalized = colorToolkit.normalize(prompt?.color);
        const key = normalized ? normalized.toLowerCase() : 'none';
        const bucket = buckets.get(key);
        if (bucket) {
            bucket.push(prompt);
        } else {
            buckets.set(key, [prompt]);
        }
    }

    const results: PromptGroup[] = [];
    for (const { key, value } of colorToolkit.groups) {
        const promptsForKey = buckets.get(key);
        if (!isArray(promptsForKey) || promptsForKey.length === 0) {
            continue;
        }
        const heading = isNullOrUndefined(value) ? i18n.t('prompts.colors.none') : colorToolkit.getLabel(value);
        results.push({ heading, prompts: promptsForKey });
    }
    return results;
};

const formatShortRelativePromptTime = (elapsedMs: number): string | null => {
    if (!isFiniteNumber(elapsedMs) || elapsedMs < 0 || elapsedMs >= PROMPT_RELATIVE_TIMESTAMP_LIMIT_MS) {
        return null;
    }
    const minutes = Math.max(1, Math.floor(msToMinutes(elapsedMs)));
    if (minutes < 60) {
        return i18n.t('prompts.time.minutesAgo', { count: minutes });
    }
    return i18n.t('prompts.time.hoursAgo', { count: Math.floor(minutes / 60) });
};

export const formatRelativeTime = (timestamp: number): string => {
    const date = new Date(timestamp);
    const nowMs = serverEpochMs();
    const bucket = resolveLocalCalendarBucket(date, new Date(nowMs));
    const relativeTime = formatShortRelativePromptTime(nowMs - timestamp);
    const displayTime = relativeTime ?? bucket.timeSecond;

    if (bucket.type === 'today') {
        return i18n.t('prompts.time.todayWithTime', { time: displayTime });
    }
    if (bucket.type === 'yesterday') {
        return i18n.t('prompts.time.yesterdayWithTime', { time: displayTime });
    }
    if (bucket.type === 'recent') {
        return i18n.t('prompts.time.daysAgoWithTime', { count: bucket.calendarDaysAgo, time: displayTime });
    }
    return formatDateTimeSecond(date);
};

export const sanitizeFilenameCandidate = (name: string | null | undefined, fallback: string = 'prompt'): string => {
    return sanitizeDownloadFilename(name, fallback);
};
