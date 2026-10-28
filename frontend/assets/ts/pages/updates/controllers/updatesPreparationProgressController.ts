/* SoAI - Update preparation progress and notice transition [frontend/assets/ts/pages/updates/controllers/updatesPreparationProgressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import type { OperationEvent } from '@core/realtime/streammanager/types.ts';
import { preparationMessage } from '@core/tasks/softwareUpdateProgress.ts';
import { taskProgressPayloadToOperationProgress } from '@core/operationprogress/taskProgressAdapter.ts';
import type { OperationProgressReporter } from '@core/operationprogress/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { LifecycleScope, type LifecycleRun } from '@core/lifecycle/lifecycleScope.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';
import type { UpdatesUiRefs } from '@pages/updates/types.ts';

interface UpdatesPreparationProgressDependencies {
    ui: Pick<UpdatesUiRefs, 'pageNotice' | 'pageNoticeBody' | 'pageProgress'>;
    createReporter(container: HTMLElement): OperationProgressReporter;
    subscribeOperations(listener: (event: OperationEvent) => void): () => void;
    reconcileOperations(): Promise<void>;
}

const PROGRESS_KEY = 'software-update';
class UpdatesPreparationProgressController {
    readonly #dependencies: UpdatesPreparationProgressDependencies;
    #reporter: OperationProgressReporter | null = null;
    #unsubscribe: (() => void) | null = null;
    #animation: Animation | null = null;
    readonly #scope = new LifecycleScope();
    #running = false;

    constructor(dependencies: UpdatesPreparationProgressDependencies) {
        this.#dependencies = dependencies;
    }

    start(): void {
        if (this.#running) return;
        this.#running = true;
        const run = this.#scope.begin('update-preparation-progress-start');
        this.#reporter = this.#dependencies.createReporter(this.#dependencies.ui.pageProgress);
        this.#reporter.update(PROGRESS_KEY, {
            message: preparationMessage('preparing'),
            state: 'pending',
            indeterminate: true,
            cancelable: false
        });
        void this.#showProgress(run).catch((error) => this.#handleProgressError(ensureError(error), run));
        this.#unsubscribe = this.#dependencies.subscribeOperations((event) => {
            if (!this.#running || !this.#scope.isCurrent(run) || event.type !== PROGRESS_KEY || (event.status !== 'start' && event.status !== 'progress')) return;
            const data = taskProgressPayloadToOperationProgress({ message: event.meta?.['statusMessage'] ?? '', details: event.meta?.['details'] ?? '', ...event.data });
            this.#reporter?.update(PROGRESS_KEY, { ...data, state: 'pending', cancelable: false, indeterminate: event.data?.['indeterminate'] === true || (event.data?.['indeterminate'] === undefined && event.meta?.['indeterminate'] !== false) });
        });
        void this.#dependencies.reconcileOperations().catch((error) => this.#handleProgressError(ensureError(error), run));
    }

    stop(): void {
        this.#running = false;
        this.#scope.abort('update-preparation-progress-stop');
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.#animation?.cancel();
        this.#animation = null;
        const ui = this.#dependencies.ui;
        this.#clearNoticeHeight();
        ui.pageNoticeBody.style.removeProperty('opacity');
        ui.pageProgress.style.removeProperty('opacity');
        ui.pageProgress.classList.add('u-hidden');
        ui.pageNoticeBody.classList.remove('u-hidden');
        this.#reporter?.destroy();
        this.#reporter = null;
    }

    destroy(): void {
        this.stop();
    }

    async #animate(element: HTMLElement, keyframes: Keyframe[], milliseconds: number, signal: AbortSignal): Promise<void> {
        if (milliseconds === 0 || element.ownerDocument.visibilityState === 'hidden' || typeof element.animate !== 'function') return;
        const animation = element.animate(keyframes, { duration: milliseconds, easing: 'ease', fill: 'forwards' });
        this.#animation = animation;
        try {
            await waitForElementAnimations(element, { ensureStarted: false, signal, animations: [animation] });
        } catch (error) {
            if (animation.playState !== 'idle') throw ensureError(error);
        }
        if (this.#animation === animation) {
            this.#animation = null;
            animation.cancel();
        }
    }

    #handleProgressError(error: Error, run: LifecycleRun): void {
        if (!this.#running || !this.#scope.isCurrent(run)) return;
        errorHandler.warn('Updates', 'Update preparation progress failed', error);
        this.#animation?.cancel();
        this.#animation = null;
        const ui = this.#dependencies.ui;
        this.#clearNoticeHeight();
        ui.pageProgress.style.removeProperty('opacity');
        ui.pageNoticeBody.classList.add('u-hidden');
        ui.pageProgress.classList.remove('u-hidden');
    }

    #clearNoticeHeight(): void {
        const notice = this.#dependencies.ui.pageNotice;
        notice.style.removeProperty('height');
        notice.style.removeProperty('overflow');
        notice.style.removeProperty('box-sizing');
    }

    async #showProgress(run: LifecycleRun): Promise<void> {
        const ui = this.#dependencies.ui;
        const fadeDuration = scaleAnimationDurationMs(160, ui.pageNotice);
        const morphDuration = scaleAnimationDurationMs(220, ui.pageNotice);
        await this.#animate(ui.pageNoticeBody, [{ opacity: 1 }, { opacity: 0 }], fadeDuration, run.signal);
        if (!this.#scope.isCurrent(run)) return;
        const previousHeight = measureLayoutBox(ui.pageNotice).height;
        ui.pageNoticeBody.classList.add('u-hidden');
        ui.pageProgress.classList.remove('u-hidden');
        ui.pageProgress.style.setProperty('opacity', '0');
        const nextHeight = measureLayoutBox(ui.pageNotice).height;
        ui.pageNotice.style.setProperty('box-sizing', 'border-box');
        ui.pageNotice.style.setProperty('height', `${previousHeight}px`);
        ui.pageNotice.style.setProperty('overflow', 'hidden');
        await this.#animate(ui.pageNotice, [{ height: `${previousHeight}px` }, { height: `${nextHeight}px` }], morphDuration, run.signal);
        if (!this.#scope.isCurrent(run)) return;
        this.#clearNoticeHeight();
        await this.#animate(ui.pageProgress, [{ opacity: 0 }, { opacity: 1 }], fadeDuration, run.signal);
        if (this.#scope.isCurrent(run)) {
            ui.pageProgress.style.removeProperty('opacity');
            ui.pageNoticeBody.style.removeProperty('opacity');
        }
    }
}

export { UpdatesPreparationProgressController };
