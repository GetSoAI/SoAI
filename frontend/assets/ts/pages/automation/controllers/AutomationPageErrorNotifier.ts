/* SoAI - Automation page error notifier [frontend/assets/ts/pages/automation/controllers/AutomationPageErrorNotifier.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractErrorCode } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createDedupingOperationFailureReporter, type DedupingOperationFailureReporter } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface AutomationPageErrorNotifierDependencies {
    showNotification: (message: string, type?: NotificationType) => void;
}

const AUTOMATION_ONE_SHOT_START_NOT_FUTURE_CODE = 'automation_one_shot_start_not_future';

const resolveAutomationOperationErrorMessage = (error: Error): string | null => {
    if (extractErrorCode(error) === AUTOMATION_ONE_SHOT_START_NOT_FUTURE_CODE) {
        return i18n.t('automation.errors.oneShotStartNotFuture');
    }
    return null;
};

class AutomationPageErrorNotifier {
    readonly #reporter: DedupingOperationFailureReporter;

    constructor(dependencies: AutomationPageErrorNotifierDependencies) {
        this.#reporter = createDedupingOperationFailureReporter({
            host: {
                showNotification: (message): void => dependencies.showNotification(message, 'error')
            }
        });
    }

    notifyErrorOnce(error: Error): void {
        this.#reporter.report(error, { errorMessage: resolveAutomationOperationErrorMessage(error) });
    }
}

export { AutomationPageErrorNotifier, resolveAutomationOperationErrorMessage };
