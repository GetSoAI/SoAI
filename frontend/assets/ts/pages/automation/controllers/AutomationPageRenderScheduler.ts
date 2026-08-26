/* SoAI - Automation page render scheduler [frontend/assets/ts/pages/automation/controllers/AutomationPageRenderScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { AutomationPageErrorNotifier } from '@pages/automation/controllers/AutomationPageErrorNotifier.ts';
import { AutomationUserNotifiedError } from '@pages/automation/controllers/AutomationUserNotifiedError.ts';

interface AutomationPageRenderSchedulerDependencies {
    requestAnimationFrame: (callback: () => void) => number;
    runWithBoundary: <T>(operation: string, task: () => Promise<T> | T) => Promise<T>;
    isDestroyed: () => boolean;
    render: () => void;
    errorNotifier: AutomationPageErrorNotifier;
}

class AutomationPageRenderScheduler {
    readonly #dependencies: AutomationPageRenderSchedulerDependencies;
    readonly #queue: AnimationFrameRenderQueue<boolean>;

    constructor(dependencies: AutomationPageRenderSchedulerDependencies) {
        this.#dependencies = dependencies;
        this.#queue = new AnimationFrameRenderQueue({
            label: 'AutomationPageRenderScheduler',
            render: () => this.#render(),
            merge: () => true,
            isDisposed: () => this.#dependencies.isDestroyed(),
            requestAnimationFrame: (callback) => this.#dependencies.requestAnimationFrame(callback)
        });
    }

    queue(): void {
        this.#queue.schedule(true);
    }

    async waitForIdle(): Promise<void> {
        await this.#queue.waitForIdle();
    }

    #render(): void {
        terminateHandledPromise(
            this.#dependencies.runWithBoundary('automation:render', () => {
                try {
                    this.#dependencies.render();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    if (!(runtimeError instanceof AutomationUserNotifiedError)) {
                        this.#dependencies.errorNotifier.notifyErrorOnce(runtimeError);
                    }
                    throw runtimeError;
                }
            })
        );
    }
}

export { AutomationPageRenderScheduler };
