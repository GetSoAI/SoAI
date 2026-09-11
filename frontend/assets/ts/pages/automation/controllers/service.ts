/* SoAI - Automation page controllers service [frontend/assets/ts/pages/automation/controllers/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import { resolveAutomationOperationErrorMessage } from '@pages/automation/controllers/AutomationPageErrorNotifier.ts';
import { saveAutomationCreateDefaults } from '@pages/automation/state/AutomationCreateDefaultsManager.ts';
import type { AutomationDataService, CreateAutomationPayload } from '@features/automation/public.ts';

interface AutomationEditorSaveModalPort {
    readAndValidate(): { payload: CreateAutomationPayload; editingAutomationId: string | null } | null;
    close(): void;
}

interface AutomationEditorSaveFlowArguments {
    modal: AutomationEditorSaveModalPort;
    modalSessionToken: number;
    isModalSessionActive(token: number): boolean;
    dataService: AutomationDataService;
    storage: StorageService;
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
}

const performAutomationEditorSave = async (inputArguments: AutomationEditorSaveFlowArguments): Promise<void> => {
    const result = inputArguments.modal.readAndValidate();
    if (!result) {
        return;
    }
    const { editingAutomationId, payload } = result;
    try {
        const savedAutomation = editingAutomationId ? await inputArguments.dataService.updateAutomation(editingAutomationId, payload) : await inputArguments.dataService.createAutomation(payload);
        saveAutomationCreateDefaults(inputArguments.storage, savedAutomation);
    } catch (error) {
        const runtimeError = ensureError(error);
        showOperationFailureNotification({
            error: runtimeError,
            operation: i18n.t('common.save'),
            errorMessage: resolveAutomationOperationErrorMessage(runtimeError),
            showNotification: (message, level): void => inputArguments.showNotification(message, level)
        });
        errorHandler.error('AutomationEditorController', 'Failed to save automation', runtimeError);
        return;
    }

    if (inputArguments.isModalSessionActive(inputArguments.modalSessionToken)) {
        inputArguments.modal.close();
    }

    try {
        await inputArguments.refreshData();
    } catch (error) {
        const refreshError = ensureError(error);
        showOperationFailureNotification({
            error: refreshError,
            operation: i18n.t('common.refresh'),
            showNotification: (message, level): void => inputArguments.showNotification(message, level)
        });
        errorHandler.error('AutomationEditorController', 'Refresh failed after saving automation', refreshError);
        return;
    }

    inputArguments.showNotification(editingAutomationId ? i18n.t('automation.notifications.updated') : i18n.t('automation.notifications.created'), 'success');
};

export { performAutomationEditorSave };
