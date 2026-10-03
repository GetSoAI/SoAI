/* SoAI - Automation page data loading and realtime run commits [frontend/assets/ts/pages/automation/controllers/AutomationWindowDataDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AutomationDataService, AutomationRunResponse, AutomationOccurrenceResponse } from '@features/automation/public.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

type AutomationRunCommitResult = { type: 'applied'; state: AutomationPageState } | { type: 'needs-refresh' } | { type: 'skipped' };

const sortZonesBySchedule = (zones: readonly AutomationOccurrenceResponse[]): AutomationOccurrenceResponse[] => zones.slice().sort((left, right) => left.scheduledAtMs - right.scheduledAtMs);

const loadBufferedWindowZones = async (dataService: AutomationDataService, fromUtcMs: number, toUtcMs: number, signal?: AbortSignal): Promise<AutomationOccurrenceResponse[]> => {
    const pageZones: AutomationOccurrenceResponse[] = [];
    let offset = 0;
    while (true) {
        throwIfAborted(signal);
        const page = await dataService.getZonesWindow(fromUtcMs, toUtcMs, offset, signal);
        throwIfAborted(signal);
        if (page.offset !== offset) {
            throw new Error('Automation occurrences page returned an invalid offset');
        }
        if (page.occurrences.length > page.limit) {
            throw new Error('Automation occurrences page returned more items than its limit');
        }
        pageZones.push(...page.occurrences);
        if (!page.hasMore) {
            break;
        }
        if (page.nextOffset === null || page.nextOffset <= offset) {
            throw new Error('Automation occurrences page returned an invalid nextOffset');
        }
        offset = page.nextOffset;
    }
    return sortZonesBySchedule(pageZones);
};

const applyAutomationRunRecord = (state: AutomationPageState, bufferedWindow: { fromUtcMs: number; toUtcMs: number }, record: AutomationRunResponse): AutomationRunCommitResult => {
    if (record.scheduledAtMs < bufferedWindow.fromUtcMs || record.scheduledAtMs >= bufferedWindow.toUtcMs) {
        return { type: 'skipped' };
    }
    const existingIndex = state.zones.findIndex((zone) => zone.runId === record.runId || (zone.automationId === record.automationId && zone.scheduledAtMs === record.scheduledAtMs));
    const existingZone = existingIndex >= 0 ? (state.zones[existingIndex] ?? null) : null;
    const title = record.title ?? existingZone?.title ?? null;
    const enabled = record.enabled ?? existingZone?.enabled ?? null;
    if (title === null || enabled === null) {
        return { type: 'needs-refresh' };
    }
    const nextZone: AutomationOccurrenceResponse = {
        automationId: record.automationId,
        scheduledAtMs: record.scheduledAtMs,
        title,
        enabled,
        color: record.color,
        runId: record.runId,
        status: record.status,
        resultExcerpt: record.resultExcerpt,
        statusMessage: record.statusMessage,
        convId: record.convId,
        startedAtActualMs: record.startedAtActualMs,
        finishedAtMs: record.finishedAtMs
    };
    const nextZones = state.zones.slice();
    if (existingIndex >= 0) {
        nextZones[existingIndex] = nextZone;
    } else {
        nextZones.push(nextZone);
    }
    return { type: 'applied', state: { ...state, zones: sortZonesBySchedule(nextZones) } };
};

export { applyAutomationRunRecord, loadBufferedWindowZones };
