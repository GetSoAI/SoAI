/* SoAI - Automation editor schedule preview and one-time start guidance [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationSchedulePreviewController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, readApiErrorField } from '@core/apiError.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { debounce } from '@core/primitives/timing.ts';
import { parseLocalDateTimeParts } from '@core/time/localDateTime.ts';
import { resolveBrowserTimezone } from '@core/timezones/timezones.ts';
import type { AutomationSchedulePreviewResponse, AutomationSchedulePreviewRequest } from '@features/automation/public.ts';
import { resolveAutomationRecurrence } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';
import { formatAutomationRunWhen, formatAutomationStartLocal } from '@pages/automation/formatting/service.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

const AUTOMATION_CONFIGURATION_SCHEDULE_PREVIEW_EVENT = 'automation:configuration:schedule-preview';
const SCHEDULE_PREVIEW_DEBOUNCE_MS = 300;

interface AutomationScheduleInputs {
    startLocal: string;
    timezone: string;
    recurrence: string;
}

interface AutomationSchedulePreviewControllerDependencies {
    summary: HTMLElement;
    eventTarget: HTMLElement;
    readSchedule: () => AutomationScheduleInputs;
    isEnabled: () => boolean;
    previewSchedule: (input: AutomationSchedulePreviewRequest, signal?: AbortSignal) => Promise<AutomationSchedulePreviewResponse>;
    getCalendarSettings: () => AutomationCalendarSettings;
}

interface ResolvedPreviewRequest {
    key: string;
    input: AutomationSchedulePreviewRequest;
}

class AutomationSchedulePreviewController {
    readonly #dependencies: AutomationSchedulePreviewControllerDependencies;
    readonly #requests = new LatestRequestController();
    readonly #requestDebounced = debounce(() => terminateHandledPromise(this.#request()), SCHEDULE_PREVIEW_DEBOUNCE_MS);
    #invalidInput: { key: string; field: string } | null = null;
    #latest: { key: string; preview: AutomationSchedulePreviewResponse } | null = null;
    #persisted: { key: string; nextRunAtMs: number | null } | null = null;

    constructor(dependencies: AutomationSchedulePreviewControllerDependencies) {
        this.#dependencies = dependencies;
    }

    refresh(): void {
        this.#requests.invalidate();
        this.#latest = null;
        this.#invalidInput = null;
        this.#dependencies.summary.textContent = '';
        this.#notifyResolved();
        this.#requestDebounced();
    }

    preserveSchedule(input: AutomationSchedulePreviewRequest, nextRunAtMs: number | null): void {
        this.#persisted = { key: JSON.stringify(input), nextRunAtMs };
    }

    reset(): void {
        this.#requestDebounced.cancel();
        this.#requests.invalidate();
        this.#latest = null;
        this.#invalidInput = null;
        this.#persisted = null;
        this.#dependencies.summary.textContent = '';
    }

    getTimezoneIssue(): string | null {
        return this.#invalidInput?.key === this.#resolveRequest()?.key && this.#invalidInput?.field === 'timezone' ? i18n.t('automation.modal.validation.timezoneInvalid') : null;
    }

    getScheduleIssue(): string | null {
        if (this.#invalidInput?.key === this.#resolveRequest()?.key && this.#invalidInput?.field === 'start') return i18n.t('automation.modal.validation.startInvalid');
        const current = this.#resolveRequest();
        const latest = this.#latest;
        if (!current || !current.input.enabled || this.#persisted?.key === current.key || !latest || latest.key !== current.key) {
            return null;
        }
        return latest.preview.oneShotStartInPast ? i18n.t('automation.errors.oneShotStartNotFuture') : null;
    }

    #resolveRequest(): ResolvedPreviewRequest | null {
        const schedule = this.#dependencies.readSchedule();
        const recurrence = resolveAutomationRecurrence(schedule.recurrence);
        if (!recurrence || !schedule.timezone || parseLocalDateTimeParts(schedule.startLocal) === null) {
            return null;
        }
        const input: AutomationSchedulePreviewRequest = { startLocal: schedule.startLocal, timezone: schedule.timezone, recurrence, enabled: this.#dependencies.isEnabled() };
        return { key: JSON.stringify(input), input };
    }

    async #request(): Promise<void> {
        const current = this.#resolveRequest();
        if (!current) {
            this.#latest = null;
            this.#invalidInput = null;
            this.#dependencies.summary.textContent = '';
            this.#notifyResolved();
            return;
        }
        await this.#requests.runLatest(async (run) => {
            try {
                const preview = await raceWithAbortSignal(this.#dependencies.previewSchedule(current.input, run.signal), run.signal);
                if (run.isStale() || this.#resolveRequest()?.key !== current.key) return;
                this.#latest = { key: current.key, preview };
                const persisted = this.#persisted;
                const displayed = persisted?.key === current.key ? { ...preview, nextOccurrenceAtMs: persisted.nextRunAtMs } : preview;
                this.#dependencies.summary.textContent = this.#describe(displayed, current.input.enabled);
            } catch (error) {
                if (run.isStale() || this.#resolveRequest()?.key !== current.key) return;
                this.#latest = null;
                this.#invalidInput = null;
                const runtimeError = ensureError(error);
                const field = runtimeError instanceof APIError && runtimeError.status === 422 ? readApiErrorField(readApiErrorField(runtimeError.payload, 'error'), 'field') : null;
                if (field === 'timezone' || field === 'start' || field === 'recurrence') {
                    this.#invalidInput = { key: current.key, field };
                    this.#dependencies.summary.textContent = field === 'timezone' ? i18n.t('automation.modal.validation.timezoneInvalid') : field === 'start' ? i18n.t('automation.modal.validation.startInvalid') : i18n.t('automation.modal.validation.recurrenceInvalid');
                } else {
                    this.#dependencies.summary.textContent = i18n.t('automation.modal.schedule.unavailable');
                    errorHandler.debug('AutomationSchedulePreviewController', 'Automation schedule preview unavailable', runtimeError);
                }
            }
            if (run.isCurrent()) this.#notifyResolved();
        });
    }

    #describe(preview: AutomationSchedulePreviewResponse, enabled: boolean): string {
        const settings = this.#dependencies.getCalendarSettings();
        const lines: string[] = [];
        if (preview.startLocalResolution === 'nonexistent') {
            lines.push(i18n.t('automation.modal.schedule.shiftedForward', { start: formatAutomationStartLocal(preview.startLocal, settings), effective: formatAutomationStartLocal(preview.effectiveStartLocal, settings), timezone: preview.timezone }));
        }
        if (preview.startLocalResolution === 'ambiguous') {
            lines.push(i18n.t('automation.modal.schedule.ambiguous', { start: formatAutomationStartLocal(preview.startLocal, settings), timezone: preview.timezone }));
        }
        if (!enabled) {
            lines.push(i18n.t('automation.modal.schedule.disabled'));
        } else if (preview.nextOccurrenceAtMs !== null) {
            const when = formatAutomationRunWhen(preview.nextOccurrenceAtMs, settings, preview.timezone);
            const browserTimezone = resolveBrowserTimezone();
            lines.push(preview.timezone === browserTimezone ? i18n.t('automation.modal.schedule.nextRun', { when, timezone: preview.timezone }) : i18n.t('automation.modal.schedule.nextRunLocal', { when, timezone: preview.timezone, localWhen: formatAutomationRunWhen(preview.nextOccurrenceAtMs, settings) }));
        }
        return lines.join('\n');
    }

    #notifyResolved(): void {
        this.#dependencies.eventTarget.dispatchEvent(new CustomEvent(AUTOMATION_CONFIGURATION_SCHEDULE_PREVIEW_EVENT, { bubbles: true }));
    }
}

export { AUTOMATION_CONFIGURATION_SCHEDULE_PREVIEW_EVENT, AutomationSchedulePreviewController };
export type { AutomationScheduleInputs };
