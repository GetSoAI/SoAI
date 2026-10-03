/* SoAI - Automation page occurrence modal controller [frontend/assets/ts/pages/automation/controllers/AutomationOccurrenceModalController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton } from '@core/dom/narrowElement.ts';
import { setControlDisabledState, setControlDisabledStateForEach } from '@core/ui/controls/disabledState.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { LatestRequestController } from '@core/concurrency/latestRequest.ts';
import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import type { SyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { AUTOMATION_OCCURRENCE_MODAL_ID, type AutomationDataService, type AutomationOccurrenceResponse } from '@features/automation/public.ts';
import { loadBufferedWindowZones } from '@pages/automation/controllers/AutomationWindowDataDomain.ts';
import { buildAutomationZoneKeyForZone, resolveAutomationZoneByKey } from '@pages/automation/contracts/zoneKey.ts';
import { AutomationOccurrenceTimelineController, renderAutomationHighlightedContent } from '@pages/automation/controllers/AutomationOccurrenceTimelineController.ts';
import { formatAutomationRunStatusLabel, resolveAutomationRunExcerpt, resolveAutomationRunStatusBadgeClass } from '@pages/automation/controllers/automationZoneFormatters.ts';
import { formatAutomationRunWhen } from '@pages/automation/formatting/service.ts';
import type { AutomationCalendarSettings } from '@pages/automation/types.ts';

interface AutomationOccurrenceModalControllerDependencies {
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    modalPresenter: ModalPresenterApi;
    syntaxHighlighter: SyntaxHighlighter;
    dataService: AutomationDataService;
}

interface RenderedOccurrence {
    zone: AutomationOccurrenceResponse;
    calendarSettings: AutomationCalendarSettings;
}

const STATUS_BADGE_CLASSES = ['status-green', 'status-red', 'status-orange', 'status-grey'];

class AutomationOccurrenceModalController {
    readonly #dependencies: AutomationOccurrenceModalControllerDependencies;
    readonly #modalId = AUTOMATION_OCCURRENCE_MODAL_ID;
    readonly #modalRoot: HTMLElement;
    readonly #title: HTMLElement;
    readonly #when: HTMLElement;
    readonly #status: HTMLElement;
    readonly #excerpt: HTMLElement;
    readonly #deleteRunButton: HTMLButtonElement;
    readonly #openTranscriptButton: HTMLButtonElement;
    readonly #viewTaskButton: HTMLButtonElement;
    readonly #timeline: AutomationOccurrenceTimelineController;
    #rendered: RenderedOccurrence | null = null;
    readonly #lookup = new LatestRequestController();
    #missingZones: readonly AutomationOccurrenceResponse[] | null = null;
    #connected = true;
    #unavailable = false;
    #unsubscribe: (() => void) | null = null;

    constructor(dependencies: AutomationOccurrenceModalControllerDependencies) {
        this.#dependencies = dependencies;
        this.#modalRoot = dependencies.modalPresenter.requireElement(this.#modalId);
        this.#title = this.#require('occurrence-title');
        this.#when = this.#require('when');
        this.#status = this.#require('status');
        this.#excerpt = this.#require('excerpt');
        this.#deleteRunButton = narrowButton(this.#require('delete-run'), 'Automation occurrence delete button');
        this.#openTranscriptButton = narrowButton(this.#require('open-transcript'), 'Automation occurrence transcript button');
        this.#viewTaskButton = narrowButton(this.#require('view-task'), 'Automation occurrence view task button');
        this.#timeline = new AutomationOccurrenceTimelineController({ plan: this.#require('plan'), todo: this.#require('todo'), syntaxHighlighter: dependencies.syntaxHighlighter });
    }

    connect(signal: AbortSignal, onClosed: (zoneKey: string) => void): void {
        const handleClose = (): void => {
            const rendered = this.#rendered;
            this.#release();
            if (rendered !== null) onClosed(buildAutomationZoneKeyForZone(rendered.zone));
        };
        this.#modalRoot.addEventListener('core.modal.close', handleClose, { signal });
        this.#connected = getWebSocketClient().isConnected();
        this.#unsubscribe?.();
        this.#unsubscribe = subscribeManagedWebSocketContracts({
            label: 'AutomationOccurrenceModal',
            signal,
            events: [
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.disconnected,
                    handler: () => {
                        this.#connected = false;
                        this.#lookup.invalidate();
                        if (this.#rendered !== null) this.#markUnavailable();
                    }
                }),
                createWebSocketContractBinding({
                    contract: WEBSOCKET_EVENT_CONTRACTS.lifecycle.connected,
                    handler: () => {
                        this.#connected = true;
                        if (this.#rendered !== null) this.#resolveMissing(this.#rendered, this.#rendered.calendarSettings);
                    }
                })
            ]
        });
    }

    open(zone: AutomationOccurrenceResponse, calendarSettings: AutomationCalendarSettings): void {
        this.#release();
        this.#render(zone, calendarSettings);
        if (!this.#connected) this.#markUnavailable();
        this.#timeline.show(zone.convId);
        this.#dependencies.modalPresenter.open(this.#modalId);
    }

    syncZones(zones: readonly AutomationOccurrenceResponse[], calendarSettings: AutomationCalendarSettings, snapshotCurrent: boolean): void {
        const rendered = this.#rendered;
        if (rendered === null || !this.isOpen()) {
            return;
        }
        if (!this.#connected || !snapshotCurrent) return;
        const zone = resolveAutomationZoneByKey(zones, buildAutomationZoneKeyForZone(rendered.zone));
        if (zone === null) {
            if (this.#missingZones !== zones) {
                this.#missingZones = zones;
                this.#resolveMissing(rendered, calendarSettings);
            }
            return;
        }
        const wasMissing = this.#missingZones !== null || this.#unavailable;
        this.#lookup.invalidate();
        this.#missingZones = null;
        if (!wasMissing && deepEqual(zone, rendered.zone) && deepEqual(calendarSettings, rendered.calendarSettings)) {
            return;
        }
        this.#render(zone, calendarSettings);
        if (zone.convId !== this.#timeline.getConversationId()) {
            this.#timeline.show(zone.convId);
        }
    }

    close(): void {
        this.#dependencies.modalPresenter.close(this.#modalId);
        this.#release();
    }

    destroy(): void {
        this.#release();
        this.#unsubscribe?.();
        this.#unsubscribe = null;
    }

    isOpen(): boolean {
        return this.#dependencies.modalPresenter.isOpen(this.#modalId);
    }

    #render(zone: AutomationOccurrenceResponse, calendarSettings: AutomationCalendarSettings): void {
        this.#unavailable = false;
        this.#rendered = { zone, calendarSettings };
        this.#title.textContent = zone.title;
        this.#when.textContent = formatAutomationRunWhen(zone.scheduledAtMs, calendarSettings);
        this.#status.textContent = formatAutomationRunStatusLabel(zone.status);
        this.#status.dataset['runStatus'] = zone.status;
        this.#status.classList.remove(...STATUS_BADGE_CLASSES);
        this.#status.classList.add(resolveAutomationRunStatusBadgeClass(zone.status));
        const excerpt = resolveAutomationRunExcerpt(zone);
        if (excerpt) {
            renderAutomationHighlightedContent(this.#excerpt, excerpt, this.#dependencies.syntaxHighlighter);
        } else {
            this.#excerpt.textContent = i18n.t('automation.pane.details.noExcerpt');
            this.#excerpt.classList.add('is-empty');
        }
        this.#deleteRunButton.dataset['zoneKey'] = buildAutomationZoneKeyForZone(zone);
        this.#openTranscriptButton.dataset['conversationId'] = zone.convId ?? '';
        this.#viewTaskButton.dataset['automationId'] = zone.automationId;
        setControlDisabledStateForEach([this.#deleteRunButton, this.#viewTaskButton], false);
        setControlDisabledState(this.#openTranscriptButton, zone.convId === null);
    }

    #release(): void {
        this.#lookup.invalidate();
        this.#missingZones = null;
        this.#rendered = null;
        this.#timeline.clear();
        this.#deleteRunButton.dataset['zoneKey'] = '';
        this.#openTranscriptButton.dataset['conversationId'] = '';
        this.#viewTaskButton.dataset['automationId'] = '';
        setControlDisabledStateForEach([this.#deleteRunButton, this.#openTranscriptButton, this.#viewTaskButton], true);
    }

    #markUnavailable(): void {
        this.#unavailable = true;
        this.#status.textContent = i18n.t('automation.toolbar.staleData');
        setControlDisabledStateForEach([this.#deleteRunButton, this.#openTranscriptButton, this.#viewTaskButton], true);
    }

    #resolveMissing(rendered: RenderedOccurrence, calendarSettings: AutomationCalendarSettings): void {
        this.#unavailable = true;
        this.#status.textContent = i18n.t('common.loading');
        setControlDisabledStateForEach([this.#deleteRunButton, this.#openTranscriptButton, this.#viewTaskButton], true);
        this.#lookup
            .runLatest(async (run) => {
                try {
                    const zones = await raceWithAbortSignal(loadBufferedWindowZones(this.#dependencies.dataService, rendered.zone.scheduledAtMs, rendered.zone.scheduledAtMs + 1, run.signal), run.signal);
                    if (!run.isCurrent() || !this.isOpen()) return;
                    const zone = resolveAutomationZoneByKey(zones, buildAutomationZoneKeyForZone(rendered.zone));
                    if (zone === null) this.close();
                    else {
                        this.#render(zone, calendarSettings);
                        if (zone.convId !== this.#timeline.getConversationId()) this.#timeline.show(zone.convId);
                    }
                } catch (error) {
                    if (!run.isCurrent()) return;
                    this.#status.textContent = i18n.t('automation.toolbar.staleData');
                    this.#excerpt.textContent = i18n.t('automation.pane.details.noExcerpt');
                    errorHandler.warn('AutomationOccurrenceModalController', 'Occurrence lookup failed', ensureError(error));
                }
            })
            .catch((error) => errorHandler.error('AutomationOccurrenceModalController', 'Occurrence resolution failed', ensureError(error)));
    }

    #require(token: string): HTMLElement {
        return this.#dependencies.requireHTMLElement(modalUiSelector(this.#modalId, token), this.#modalRoot);
    }
}

export { AutomationOccurrenceModalController };
