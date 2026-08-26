/* SoAI - Prompts page mappers prompt stats domain [frontend/assets/ts/pages/prompts/mappers/promptStatsDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatCalendarLabelWithFullDate, formatDateTimeMinute } from '@core/primitives/dateTime.ts';
import { resolveLocalCalendarBucket } from '@core/time/localCalendar.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { isArray } from '@core/typeGuards.ts';
import type { PromptRecord } from '@features/prompts/public.ts';
import type { ColorToolkitInterface } from '@pages/prompts/contracts/contracts.ts';

interface PromptStats {
    total: number;
    selectionSize: number;
    totalCharacters: number;
    specialCount: number;
    lastCreatedLabel: string;
    lastCreatedCompactLabel: string;
    lastModifiedLabel: string;
    lastModifiedCompactLabel: string;
}

type PromptEpochResolver = (prompt: PromptRecord) => number;

const resolveMostRecentEpoch = (prompts: PromptRecord[], resolveEpoch: PromptEpochResolver): number => prompts.reduce((latest: number, prompt: PromptRecord) => Math.max(latest, resolveEpoch(prompt)), 0);

const formatPromptTimestampCompactLabel = (timestamp: number, nowMs: number): string => {
    const date = new Date(timestamp);
    const bucket = resolveLocalCalendarBucket(date, new Date(nowMs));
    if (bucket.type === 'today') {
        return i18n.t('prompts.time.todayWithTime', { time: bucket.timeMinute });
    }
    if (bucket.type === 'yesterday') {
        return i18n.t('prompts.time.yesterdayWithTime', { time: bucket.timeMinute });
    }
    return formatDateTimeMinute(date);
};

const resolvePromptStatLabels = (timestamp: number, nowMs: number): { full: string; compact: string } => {
    if (timestamp <= 0) {
        const never = i18n.t('prompts.never');
        return { full: never, compact: never };
    }
    return { full: formatCalendarLabelWithFullDate(timestamp, nowMs), compact: formatPromptTimestampCompactLabel(timestamp, nowMs) };
};

export const computePromptStats = (prompts: PromptRecord[], colorToolkit: ColorToolkitInterface, selectionSize: number = 0): PromptStats => {
    const collection = isArray(prompts) ? prompts : [];
    const totalCharacters = collection.reduce((sum: number, prompt: PromptRecord) => sum + prompt.content.length, 0);
    const specialCount = collection.filter((prompt: PromptRecord) => colorToolkit.normalize(prompt.color) !== null).length;
    const currentServerEpoch = serverEpochMs();
    const created = resolvePromptStatLabels(
        resolveMostRecentEpoch(collection, (prompt) => prompt.createdAtMs),
        currentServerEpoch
    );
    const modified = resolvePromptStatLabels(
        resolveMostRecentEpoch(collection, (prompt) => Math.max(prompt.modifiedAtMs, prompt.createdAtMs)),
        currentServerEpoch
    );

    return {
        total: collection.length,
        selectionSize,
        totalCharacters,
        specialCount,
        lastCreatedLabel: created.full,
        lastCreatedCompactLabel: created.compact,
        lastModifiedLabel: modified.full,
        lastModifiedCompactLabel: modified.compact
    };
};

export type { PromptStats };
