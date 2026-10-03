/* SoAI - Automation page refresh after an applied change [frontend/assets/ts/pages/automation/controllers/AutomationMutationCompletionDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface AutomationChangeRefreshDependencies {
    refreshData: () => Promise<void>;
    showNotification: (message: string, type?: NotificationType) => void;
}

const refreshAfterAutomationChange = async (dependencies: AutomationChangeRefreshDependencies, logSource: string): Promise<void> => {
    try {
        await dependencies.refreshData();
    } catch (error) {
        if (isAbortError(ensureError(error))) return;
        errorHandler.warn(logSource, 'Refresh failed after an applied automation change', ensureError(error));
        dependencies.showNotification(i18n.t('automation.notifications.changeRefreshFailed'), 'warning');
    }
};

export { refreshAfterAutomationChange };
