/* SoAI - Update preparation progress and notice transition [frontend/assets/ts/pages/updates/controllers/updatesPreparationProgressController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import type { SoftwareUpdatePreparationResponse } from '@core/api/contracts/softwareContracts.ts';
import type { OperationProgressReporter } from '@core/operationprogress/types.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import type { UpdatesUiRefs } from '@pages/updates/types.ts';

interface UpdatesPreparationProgressDependencies {
    ui: Pick<UpdatesUiRefs, 'pageNotice' | 'pageNoticeBody' | 'pageProgress'>;
    createReporter(container: HTMLElement): OperationProgressReporter;
    getPreparation(): Promise<SoftwareUpdatePreparationResponse>;
    setTimeout(callback: () => void, milliseconds: number): number | null;
    clearTimer(timerId: number | null): void;
}

const PROGRESS_KEY = 'software-update';
const POLL_INTERVAL_MS = 500;
const DEGRADED_POLL_INTERVAL_MS = 2000;
const FAILURE_THRESHOLD = 3;

const preparationMessage = (phase: NonNullable<SoftwareUpdatePreparationResponse['phase']>): string => {
    switch (phase) {
        case 'preparing':
            return i18n.t('updates.status.updating');
        case 'fetching':
            return i18n.t('updates.status.fetching');
        case 'verifying':
            return i18n.t('updates.progress.verifying');
        case 'downloading':
            return i18n.t('updates.progress.downloading');
        case 'staging':
            return i18n.t('updates.progress.staging');
        case 'handoff':
            return i18n.t('updates.progress.handoff');
        case 'unavailable':
            return i18n.t('updates.progress.unavailable');
    }
};

class UpdatesPreparationProgressController {
    readonly #dependencies: UpdatesPreparationProgressDependencies;
    #reporter: OperationProgressReporter | null = null;
    #timerId: number | null = null;
    #animation: Animation | null = null;
    #revision = 0;
    #running = false;
    #consecutiveFailures = 0;

    constructor(dependencies: UpdatesPreparationProgressDependencies) {
        this.#dependencies = dependencies;
    }

    start(): void {
        if (this.#running) return;
        this.#running = true;
        this.#revision += 1;
        const revision = this.#revision;
        this.#consecutiveFailures = 0;
        this.#reporter = this.#dependencies.createReporter(this.#dependencies.ui.pageProgress);
        this.#reporter.update(PROGRESS_KEY, {
            message: preparationMessage('preparing'),
            state: 'pending',
            indeterminate: true,
            cancelable: false
        });
        void this.#showProgress(revision).catch((error) => this.#handleProgressError(ensureError(error), revision));
        void this.#poll(revision).catch((error) => this.#handleProgressError(ensureError(error), revision));
    }

    stop(): void {
        this.#running = false;
        this.#revision += 1;
        this.#dependencies.clearTimer(this.#timerId);
        this.#timerId = null;
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

    async #poll(revision: number): Promise<void> {
        try {
            const preparation = await this.#dependencies.getPreparation();
            if (!this.#running || revision !== this.#revision) return;
            this.#consecutiveFailures = 0;
            this.#render(preparation);
        } catch {
            if (!this.#running || revision !== this.#revision) return;
            this.#consecutiveFailures += 1;
            if (this.#consecutiveFailures >= FAILURE_THRESHOLD) {
                this.#render({ active: true, taskId: null, phase: 'unavailable', downloadedBytes: null, totalBytes: null, updatedAtMs: null });
            }
        } finally {
            if (this.#running && revision === this.#revision) {
                const delay = this.#consecutiveFailures >= FAILURE_THRESHOLD ? DEGRADED_POLL_INTERVAL_MS : POLL_INTERVAL_MS;
                this.#timerId = this.#dependencies.setTimeout(() => {
                    void this.#poll(revision).catch((error) => this.#handleProgressError(ensureError(error), revision));
                }, delay);
            }
        }
    }

    #render(preparation: SoftwareUpdatePreparationResponse): void {
        const phase = preparation.active ? (preparation.phase ?? 'preparing') : 'preparing';
        const downloadedBytes = preparation.downloadedBytes;
        const totalBytes = preparation.totalBytes;
        const measured = phase === 'downloading' && downloadedBytes !== null && totalBytes !== null && totalBytes > 0;
        const progress = measured ? { progress: Math.floor((downloadedBytes * 100) / totalBytes) } : {};
        this.#reporter?.update(PROGRESS_KEY, {
            message: preparationMessage(phase),
            details: measured ? `${formatBytes(downloadedBytes)} / ${formatBytes(totalBytes)}` : '',
            ...progress,
            indeterminate: !measured,
            state: measured ? 'downloading' : 'pending',
            cancelable: false
        });
    }

    async #animate(element: HTMLElement, keyframes: Keyframe[], milliseconds: number): Promise<void> {
        if (milliseconds === 0 || typeof element.animate !== 'function') return;
        const animation = element.animate(keyframes, { duration: milliseconds, easing: 'ease', fill: 'forwards' });
        this.#animation = animation;
        try {
            await animation.finished;
        } catch (error) {
            if (animation.playState !== 'idle') throw ensureError(error);
        }
        if (this.#animation === animation) {
            this.#animation = null;
            animation.cancel();
        }
    }

    #handleProgressError(error: Error, revision: number): void {
        if (!this.#running || revision !== this.#revision) return;
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

    async #showProgress(revision: number): Promise<void> {
        const ui = this.#dependencies.ui;
        const fadeDuration = scaleAnimationDurationMs(160, ui.pageNotice);
        const morphDuration = scaleAnimationDurationMs(220, ui.pageNotice);
        await this.#animate(ui.pageNoticeBody, [{ opacity: 1 }, { opacity: 0 }], fadeDuration);
        if (revision !== this.#revision) return;
        const previousHeight = measureLayoutBox(ui.pageNotice).height;
        ui.pageNoticeBody.classList.add('u-hidden');
        ui.pageProgress.classList.remove('u-hidden');
        ui.pageProgress.style.setProperty('opacity', '0');
        const nextHeight = measureLayoutBox(ui.pageNotice).height;
        ui.pageNotice.style.setProperty('box-sizing', 'border-box');
        ui.pageNotice.style.setProperty('height', `${previousHeight}px`);
        ui.pageNotice.style.setProperty('overflow', 'hidden');
        await this.#animate(ui.pageNotice, [{ height: `${previousHeight}px` }, { height: `${nextHeight}px` }], morphDuration);
        if (revision !== this.#revision) return;
        this.#clearNoticeHeight();
        await this.#animate(ui.pageProgress, [{ opacity: 0 }, { opacity: 1 }], fadeDuration);
        if (revision === this.#revision) {
            ui.pageProgress.style.removeProperty('opacity');
            ui.pageNoticeBody.style.removeProperty('opacity');
        }
    }
}

export { UpdatesPreparationProgressController };
