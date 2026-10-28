/* SoAI - Automation page render scheduler [frontend/assets/ts/pages/automation/controllers/AutomationPageRenderScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';

interface AutomationPageRenderSchedulerDependencies {
    run: (operation: string, task: () => Promise<void> | void) => Promise<void>;
    isDestroyed: () => boolean;
    render: () => void;
}

class AutomationPageRenderScheduler {
    readonly #queue: AnimationFrameRenderQueue<boolean>;

    constructor(dependencies: AutomationPageRenderSchedulerDependencies) {
        this.#queue = new AnimationFrameRenderQueue({
            label: 'AutomationPageRenderScheduler',
            required: true,
            render: () => dependencies.run('automation:render', () => dependencies.render()),
            merge: () => true,
            isDisposed: dependencies.isDestroyed
        });
    }

    queue(): void {
        this.#queue.schedule(true);
    }

    async waitForIdle(signal: AbortSignal | null = null): Promise<void> {
        await this.#queue.waitForIdle(signal);
    }

    dispose(): void {
        this.#queue.dispose();
    }
}

export { AutomationPageRenderScheduler };
