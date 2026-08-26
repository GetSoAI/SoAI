/* SoAI - Automation page error notifier [frontend/assets/ts/pages/automation/controllers/AutomationPageErrorNotifier.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDedupingOperationFailureReporter, type DedupingOperationFailureReporter } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface AutomationPageErrorNotifierDependencies {
    showNotification: (message: string, type?: NotificationType) => void;
}

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
        this.#reporter.report(error);
    }
}

export { AutomationPageErrorNotifier };
