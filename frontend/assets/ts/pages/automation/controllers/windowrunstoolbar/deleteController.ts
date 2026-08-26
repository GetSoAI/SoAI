/* SoAI - Automation page delete controller [frontend/assets/ts/pages/automation/controllers/windowrunstoolbar/deleteController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { normalizeAutomationZoneKeyList, parseAutomationZoneKey, resolveAutomationZoneByKey } from '@pages/automation/contracts/zoneKey.ts';
import { AutomationUserNotifiedError } from '@pages/automation/controllers/AutomationUserNotifiedError.ts';
import type { AutomationWindowRunsSelectionManager } from '@pages/automation/controllers/windowrunstoolbar/selectionManager.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

type WindowRunsDeleteDependencies = {
    dataService: AutomationDataService;
    getState: () => AutomationPageState;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType) => void;
    selection: AutomationWindowRunsSelectionManager;
};

class AutomationWindowRunsDeleteController {
    readonly #dependencies: WindowRunsDeleteDependencies;

    constructor(dependencies: WindowRunsDeleteDependencies) {
        this.#dependencies = dependencies;
    }

    deleteOne(zoneKey: string): Promise<boolean> {
        return this.#deleteKeys([zoneKey]);
    }

    async deleteSelected(): Promise<void> {
        const selected = this.#dependencies.selection.list();
        await this.#deleteKeys(selected);
    }

    async #deleteKeys(zoneKeys: readonly string[]): Promise<boolean> {
        const normalized = normalizeAutomationZoneKeyList(zoneKeys);
        if (normalized.length === 0) {
            return false;
        }

        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('automation.pane.windowRuns.confirmations.deleteTitle'),
            message: i18n.t('automation.pane.windowRuns.confirmations.deleteMessage', { count: normalized.length }),
            confirmText: i18n.t('common.delete'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        });
        if (!confirmed) {
            return false;
        }

        const occurrences = normalized.map((key) => {
            const parsed = parseAutomationZoneKey(key, 'Automation window run delete');
            return { automationId: parsed.automationId, scheduledAtMs: parsed.scheduledAtMs };
        });

        const operationLabel = i18n.t('common.delete');
        try {
            await this.#dependencies.dataService.deleteOccurrences(occurrences);
        } catch (error) {
            const runtimeError = ensureError(error);
            showOperationFailureNotification({
                error: runtimeError,
                operation: operationLabel,
                showNotification: (message, level): void => this.#dependencies.showNotification(message, level)
            });
            errorHandler.error('AutomationWindowRunsDeleteController', 'Failed to delete automation window runs', runtimeError);
            return false;
        }

        this.#dependencies.selection.deactivate();

        try {
            await this.#dependencies.refreshData();
        } catch (error) {
            const runtimeError = ensureError(error);
            showOperationFailureNotification({
                error: runtimeError,
                operation: i18n.t('common.refresh'),
                showNotification: (message, level): void => this.#dependencies.showNotification(message, level)
            });
            errorHandler.error('AutomationWindowRunsDeleteController', 'Refresh failed after deleting automation window runs', runtimeError);
            throw new AutomationUserNotifiedError(runtimeError);
        }

        const afterZones = this.#dependencies.getState().zones;
        let deletedCount = 0;
        for (const key of normalized) {
            if (!resolveAutomationZoneByKey(afterZones, key)) {
                deletedCount += 1;
            }
        }
        const notificationCount = deletedCount > 0 ? deletedCount : normalized.length;
        this.#dependencies.showNotification(i18n.t('automation.pane.windowRuns.notifications.deleteSuccess', { count: notificationCount }), 'success');
        return true;
    }
}

export { AutomationWindowRunsDeleteController };
