/* SoAI - Automation page controllers effects [frontend/assets/ts/pages/automation/controllers/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { resetAutomationPagePreferenceState } from '@pages/automation/controllers/automationPageState.ts';
import { navigateCalendar } from '@pages/automation/controllers/stateTransitions.ts';
import { resetAutomationPreferences } from '@pages/automation/state/preferences.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

interface AutomationPagePreferenceResetHost {
    storage: StorageService;
    getState: () => AutomationPageState;
    setState: (next: AutomationPageState) => void;
    applySplit: (percent: number) => void;
    initializeInteractions: () => Promise<void>;
    reconnectInteractions: () => void;
    queueRender: () => void;
    refreshData: () => Promise<void>;
    showSuccessNotification: (message: string) => void;
    clearPreferencesCorruptError: () => void;
}

interface AutomationPageScrollNavigationHost {
    getState: () => AutomationPageState;
    setState: (next: AutomationPageState) => void;
    queueRender: () => void;
    refreshDataWithBoundary: () => Promise<void>;
    cancelPendingScrollShift: () => void;
    showErrorNotification: (message: string) => void;
}

const resetAutomationPagePreferencesAndRefresh = async (host: AutomationPagePreferenceResetHost): Promise<void> => {
    resetAutomationPreferences(host.storage);
    host.clearPreferencesCorruptError();
    const nextState = resetAutomationPagePreferenceState(host.getState());
    host.setState(nextState);
    host.applySplit(nextState.splitLeftPercent);
    await host.initializeInteractions();
    host.reconnectInteractions();
    host.queueRender();
    await host.refreshData();
    host.showSuccessNotification(i18n.t('automation.notifications.preferencesReset'));
};

const shiftAutomationPageVisiblePeriod = async (host: AutomationPageScrollNavigationHost, offset: number): Promise<void> => {
    host.setState(navigateCalendar(host.getState(), offset));
    try {
        await host.refreshDataWithBoundary();
        host.queueRender();
    } catch (error) {
        const runtimeError = ensureError(error);
        host.cancelPendingScrollShift();
        host.queueRender();
        showOperationFailureNotification({
            error: runtimeError,
            operation: i18n.t('common.refresh'),
            showNotification: (message): void => host.showErrorNotification(message)
        });
        throw runtimeError;
    }
};

export { resetAutomationPagePreferencesAndRefresh, shiftAutomationPageVisiblePeriod };
