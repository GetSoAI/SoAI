/* SoAI - Automation page crud actions [frontend/assets/ts/pages/automation/controllers/automationCrudActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { AutomationEditorController } from '@pages/automation/controllers/AutomationEditorController.ts';
import { clearSelectionIfMatchesAutomation, confirmDeleteAutomation, requireCheckboxInput, resolveAutomationById, runDeleteAutomation, runToggleAutomationEnabled } from '@pages/automation/controllers/automationManagementActions.ts';
import { resolveAutomationOperationErrorMessage } from '@pages/automation/controllers/AutomationPageErrorNotifier.ts';
import { AutomationUserNotifiedError } from '@pages/automation/controllers/AutomationUserNotifiedError.ts';
import { requireAutomationToggleLabel } from '@pages/automation/dom.ts';
import type { AutomationDataService } from '@features/automation/public.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

interface AutomationCrudStatePort {
    dataService: AutomationDataService;
    getState(): AutomationPageState;
    setState(next: AutomationPageState): void;
    refreshData(): Promise<void>;
    showNotification(message: string, type?: NotificationType): void;
}

interface AutomationCrudControllerPort {
    getEditor(): AutomationEditorController | null;
    run(operation: string, task: () => Promise<void> | void): void;
}

interface AutomationCrudActionHost {
    state: AutomationCrudStatePort;
    controllers: AutomationCrudControllerPort;
}

const notifyOperationFailed = (host: AutomationCrudActionHost, operation: string, runtimeError: Error): void => {
    showOperationFailureNotification({
        error: runtimeError,
        operation,
        errorMessage: resolveAutomationOperationErrorMessage(runtimeError),
        showNotification: (message, level): void => host.state.showNotification(message, level)
    });
};

const notifyRefreshFailedAndThrow = (host: AutomationCrudActionHost, refreshError: Error): never => {
    showOperationFailureNotification({
        error: refreshError,
        operation: i18n.t('common.refresh'),
        showNotification: (message, level): void => host.state.showNotification(message, level)
    });
    errorHandler.error('AutomationCrudActions', 'Refresh failed after successful operation', refreshError);
    throw new AutomationUserNotifiedError(refreshError);
};

const handleEditAutomation = (host: AutomationCrudActionHost, automationId: string): void => {
    host.controllers.run('automation:editAutomation', async () => {
        const automation = resolveAutomationById(host.state.getState().automations, automationId);
        const editor = host.controllers.getEditor();
        if (!editor) {
            throw new Error('Automation editor is not initialized');
        }
        await editor.openEdit(automation);
    });
};

const handlePreviewAutomation = (host: AutomationCrudActionHost, automationId: string): void => {
    host.controllers.run('automation:previewAutomation', async () => {
        const automation = resolveAutomationById(host.state.getState().automations, automationId);
        const editor = host.controllers.getEditor();
        if (!editor) {
            throw new Error('Automation editor is not initialized');
        }
        await editor.openPreview(automation);
    });
};

const handleToggleAutomationEnabled = (host: AutomationCrudActionHost, element: HTMLElement, automationId: string): void => {
    const checkbox = requireCheckboxInput(element);
    const enabled = checkbox.checked;
    const row = checkbox.closest('.automation-automation-row');
    if (!(row instanceof HTMLElement)) {
        throw new Error('Automation enabled toggle must be rendered inside an automation row');
    }
    const wrapper = checkbox.closest('.toggle-switch');
    if (!(wrapper instanceof HTMLElement)) {
        throw new Error('Automation enabled toggle must be rendered inside a toggle switch wrapper');
    }
    const label = requireAutomationToggleLabel(wrapper);
    host.controllers.run('automation:toggleEnabled', async () => {
        const previous = !enabled;
        try {
            checkbox.disabled = true;
            row.classList.toggle('is-enabled', enabled);
            label.textContent = enabled ? i18n.t('common.enabled') : i18n.t('common.disabled');

            try {
                await runToggleAutomationEnabled({ dataService: host.state.dataService }, { automationId, enabled });
            } catch (error) {
                const runtimeError = ensureError(error);
                checkbox.checked = previous;
                row.classList.toggle('is-enabled', previous);
                label.textContent = previous ? i18n.t('common.enabled') : i18n.t('common.disabled');
                notifyOperationFailed(host, i18n.t('common.save'), runtimeError);
                errorHandler.error('AutomationCrudActions', 'Failed to toggle automation enabled', runtimeError);
                return;
            }

            try {
                await host.state.refreshData();
            } catch (error) {
                notifyRefreshFailedAndThrow(host, ensureError(error));
            }

            host.state.showNotification(enabled ? i18n.t('automation.notifications.enabled') : i18n.t('automation.notifications.disabled'), enabled ? 'success' : 'warning');
        } finally {
            checkbox.disabled = false;
        }
    });
};

const handleDeleteAutomation = (host: AutomationCrudActionHost, automationId: string): void => {
    host.controllers.run('automation:deleteAutomation', async () => {
        const automation = resolveAutomationById(host.state.getState().automations, automationId);
        const confirmed = await confirmDeleteAutomation({ id: automation.id, title: automation.title });
        if (!confirmed) {
            return;
        }
        try {
            await runDeleteAutomation({ dataService: host.state.dataService }, automationId);
            host.state.setState(clearSelectionIfMatchesAutomation(host.state.getState(), automationId));
        } catch (error) {
            const runtimeError = ensureError(error);
            notifyOperationFailed(host, i18n.t('common.delete'), runtimeError);
            errorHandler.error('AutomationCrudActions', 'Failed to delete automation', runtimeError);
            return;
        }

        try {
            await host.state.refreshData();
        } catch (error) {
            notifyRefreshFailedAndThrow(host, ensureError(error));
        }

        host.state.showNotification(i18n.t('automation.notifications.deleted'), 'success');
    });
};

export { handleDeleteAutomation, handleEditAutomation, handlePreviewAutomation, handleToggleAutomationEnabled };
