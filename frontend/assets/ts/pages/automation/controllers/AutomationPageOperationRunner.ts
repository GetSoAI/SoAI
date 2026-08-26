/* SoAI - Automation page operation runner [frontend/assets/ts/pages/automation/controllers/AutomationPageOperationRunner.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { AutomationPageErrorNotifier } from '@pages/automation/controllers/AutomationPageErrorNotifier.ts';
import { AutomationUserNotifiedError } from '@pages/automation/controllers/AutomationUserNotifiedError.ts';

interface AutomationPageOperationRunnerDependencies {
    runWithBoundary: <T>(operation: string, task: () => Promise<T> | T) => Promise<T>;
    errorNotifier: AutomationPageErrorNotifier;
}

class AutomationPageOperationRunner {
    readonly #dependencies: AutomationPageOperationRunnerDependencies;

    constructor(dependencies: AutomationPageOperationRunnerDependencies) {
        this.#dependencies = dependencies;
    }

    run(operation: string, task: () => Promise<void> | void): void {
        terminateHandledPromise(
            this.#dependencies.runWithBoundary(operation, async () => {
                try {
                    await task();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (runtimeError instanceof AutomationUserNotifiedError) {
                        throw runtimeError;
                    }
                    this.#dependencies.errorNotifier.notifyErrorOnce(runtimeError);
                    throw runtimeError;
                }
            })
        );
    }
}

export { AutomationPageOperationRunner };
