/* SoAI - Automation page render scheduler [frontend/assets/ts/pages/automation/controllers/AutomationPageRenderScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';

interface AutomationPageRenderSchedulerDependencies {
    requestAnimationFrame: (callback: () => void) => number;
    run: (operation: string, task: () => Promise<void> | void) => void;
    isDestroyed: () => boolean;
    render: () => void;
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
        this.#dependencies.run('automation:render', () => this.#dependencies.render());
    }
}

export { AutomationPageRenderScheduler };
