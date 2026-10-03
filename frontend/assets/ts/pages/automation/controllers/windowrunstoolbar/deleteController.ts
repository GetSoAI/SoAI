/* SoAI - Automation page delete controller [frontend/assets/ts/pages/automation/controllers/windowrunstoolbar/deleteController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { createExclusiveSaveAdmission } from '@core/save/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { buildAutomationZoneKeyForZone, normalizeAutomationZoneKeyList, resolveAutomationZoneByKey } from '@pages/automation/contracts/zoneKey.ts';
import { refreshAfterAutomationChange } from '@pages/automation/controllers/AutomationMutationCompletionDomain.ts';
import { buildAutomationWindowSignature } from '@pages/automation/controllers/automationWindow.ts';
import type { AutomationWindowRunsSelectionManager } from '@pages/automation/controllers/windowrunstoolbar/selectionManager.ts';
import type { AutomationDataService, AutomationOccurrencesDeleteResponse, AutomationOccurrenceResponse } from '@features/automation/public.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

const AUTOMATION_OCCURRENCES_DELETE_MAX_ITEMS = 5000;

type WindowRunsDeleteDependencies = {
    dataService: AutomationDataService;
    getState: () => AutomationPageState;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType) => void;
    selection: AutomationWindowRunsSelectionManager;
    onPendingChanged: (pending: boolean) => void;
};

type OccurrenceDeleteType = 'skip' | 'stop' | 'remove';

interface OccurrenceDeleteConfirmation {
    title: string;
    message: string;
    confirmText: string;
}

const resolveOccurrenceDeleteType = (zone: AutomationOccurrenceResponse, nowMs: number): OccurrenceDeleteType => {
    if (zone.status === 'queued' || zone.status === 'running') {
        return 'stop';
    }
    return zone.status === 'scheduled' && zone.scheduledAtMs > nowMs ? 'skip' : 'remove';
};

const resolveDeleteConfirmation = (targets: readonly AutomationOccurrenceResponse[]): OccurrenceDeleteConfirmation => {
    const [single] = targets;
    if (targets.length !== 1 || single === undefined) {
        return {
            title: i18n.t('automation.pane.windowRuns.confirmations.deleteTitle'),
            message: i18n.t('automation.pane.windowRuns.confirmations.deleteMessage', { count: targets.length }),
            confirmText: i18n.t('common.delete')
        };
    }
    const title = single.title;
    switch (resolveOccurrenceDeleteType(single, serverEpochMs())) {
        case 'skip':
            return { title: i18n.t('automation.pane.windowRuns.confirmations.skipTitle'), message: i18n.t('automation.pane.windowRuns.confirmations.skipMessage', { title }), confirmText: i18n.t('automation.pane.windowRuns.confirmations.skipConfirm') };
        case 'stop':
            return { title: i18n.t('automation.pane.windowRuns.confirmations.stopTitle'), message: i18n.t('automation.pane.windowRuns.confirmations.stopMessage', { title }), confirmText: i18n.t('automation.pane.windowRuns.confirmations.stopConfirm') };
        case 'remove':
            return { title: i18n.t('automation.pane.windowRuns.confirmations.removeTitle'), message: i18n.t('automation.pane.windowRuns.confirmations.removeMessage', { title }), confirmText: i18n.t('automation.pane.windowRuns.confirmations.removeConfirm') };
    }
};

class AutomationWindowRunsDeleteController {
    readonly #dependencies: WindowRunsDeleteDependencies;
    readonly #admission = createExclusiveSaveAdmission();
    #operation: AbortController | null = null;
    #disposed = false;

    constructor(dependencies: WindowRunsDeleteDependencies) {
        this.#dependencies = dependencies;
    }

    deleteOne(zoneKey: string): Promise<boolean> {
        return this.#deleteKeys(() => [zoneKey]);
    }

    async deleteSelected(): Promise<void> {
        await this.#deleteKeys(() => this.#dependencies.selection.list());
    }

    cancelPending(): void {
        this.#operation?.abort();
    }

    dispose(): void {
        this.#disposed = true;
        this.cancelPending();
    }

    async #deleteKeys(readKeys: () => readonly string[]): Promise<boolean> {
        if (this.#disposed) return false;
        const release = this.#admission.acquire();
        if (release === null) return false;
        const operation = new AbortController();
        this.#operation = operation;
        const windowSignature = buildAutomationWindowSignature(this.#dependencies.getState());
        const isCurrent = (): boolean => !operation.signal.aborted && !this.#disposed && windowSignature === buildAutomationWindowSignature(this.#dependencies.getState());
        this.#dependencies.onPendingChanged(true);
        try {
            return await this.#confirmAndDelete(readKeys, operation.signal, isCurrent);
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isAbortError(runtimeError)) return false;
            throw runtimeError;
        } finally {
            release();
            this.#operation = null;
            this.#dependencies.onPendingChanged(false);
        }
    }

    async #confirmAndDelete(readKeys: () => readonly string[], signal: AbortSignal, isCurrent: () => boolean): Promise<boolean> {
        let confirmedTargets: AutomationOccurrenceResponse[] = [];
        while (isCurrent()) {
            const targets = this.#resolveTargets(readKeys());
            if (targets.length === 0) {
                this.#dependencies.showNotification(i18n.t('automation.pane.windowRuns.notifications.nothingToDelete'), 'warning');
                return false;
            }
            if (targets.length > AUTOMATION_OCCURRENCES_DELETE_MAX_ITEMS) {
                this.#dependencies.showNotification(i18n.t('automation.pane.windowRuns.notifications.tooManySelected', { max: AUTOMATION_OCCURRENCES_DELETE_MAX_ITEMS }), 'warning');
                return false;
            }
            const confirmation = resolveDeleteConfirmation(targets);
            const meaning = this.#confirmationIdentity(targets);
            const confirmed = await raceWithAbortSignal(requireDialogsService().showConfirmation({ ...confirmation, cancelText: i18n.t('common.cancel'), variant: 'danger', signal }), signal);
            if (!confirmed || !isCurrent()) {
                return false;
            }
            confirmedTargets = this.#resolveTargets(readKeys());
            if (this.#confirmationIdentity(confirmedTargets) === meaning) break;
        }
        if (!isCurrent()) return false;
        let result: AutomationOccurrencesDeleteResponse;
        try {
            result = await this.#dependencies.dataService.deleteOccurrences(confirmedTargets.map((zone) => ({ automationId: zone.automationId, scheduledAtMs: zone.scheduledAtMs })));
        } catch (error) {
            const runtimeError = ensureError(error);
            showOperationFailureNotification({
                error: runtimeError,
                operation: i18n.t('common.delete'),
                showNotification: (message, level): void => this.#dependencies.showNotification(message, level)
            });
            errorHandler.error('AutomationWindowRunsDeleteController', 'Failed to delete automation window runs', runtimeError);
            return false;
        }
        if (isCurrent()) this.#dependencies.selection.deactivate();
        this.#dependencies.showNotification(i18n.t('automation.pane.windowRuns.notifications.deleteSuccess', { count: result.deletedOccurrenceCount }), 'success');
        if (isCurrent()) await refreshAfterAutomationChange(this.#dependencies, 'AutomationWindowRunsDeleteController');
        return true;
    }

    #confirmationIdentity(targets: readonly AutomationOccurrenceResponse[]): string {
        const nowMs = serverEpochMs();
        return JSON.stringify(targets.map((zone) => [buildAutomationZoneKeyForZone(zone), resolveOccurrenceDeleteType(zone, nowMs), zone.title, zone.runId]).sort((left, right) => String(left[0]).localeCompare(String(right[0]), 'en')));
    }

    #resolveTargets(zoneKeys: readonly string[]): AutomationOccurrenceResponse[] {
        const zones = this.#dependencies.getState().zones;
        return normalizeAutomationZoneKeyList(zoneKeys).flatMap((key) => {
            const zone = resolveAutomationZoneByKey(zones, key);
            return zone === null ? [] : [zone];
        });
    }
}

export { AutomationWindowRunsDeleteController };
