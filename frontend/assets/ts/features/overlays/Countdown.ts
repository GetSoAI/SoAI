/* SoAI - Overlays feature countdown [frontend/assets/ts/features/overlays/Countdown.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { getMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { isFunction, isNumber } from '@core/typeGuards.ts';
import { syncDeterminateProgress } from '@core/ui/progressWidths.ts';

const MODULE_ID = 'features.overlays.Countdown';
const COUNTDOWN_OVERLAY_SERVICE_ID = 'features.overlays.countdown';

interface CountdownElements {
    overlay: HTMLElement;
    titleNode: HTMLElement;
    prefixNode: HTMLElement;
    suffixNode: HTMLElement;
    valueNode: HTMLElement;
    progressNode: HTMLElement;
    cancelButton: HTMLButtonElement;
}

interface ShowOptions {
    title?: string | undefined;
    seconds?: number | undefined;
    prefixText?: string | undefined;
    suffixText?: string | undefined;
    cancelLabel?: string | undefined;
    onCancel?: CountdownCancelHandler | undefined;
    onComplete?: (() => void) | undefined;
}

type CountdownCancelHandler = () => boolean | Promise<boolean>;

class CountdownOverlay extends LifecycleModel {
    elements: CountdownElements | null = null;
    timerHandle: number | null = null;
    remainingSeconds: number = 0;
    totalSeconds: number = 0;
    cancelHandler: CountdownCancelHandler | null = null;
    completeHandler: (() => void) | null = null;
    maintenanceToken: symbol | null = null;
    cancelButtonDisposer: (() => void) | null = null;
    cancelInProgress: boolean = false;

    constructor() {
        super({ moduleId: MODULE_ID });
    }

    async initialize(): Promise<void> {
        if (this.isInitialized) {
            return;
        }
        if (this.isDestroyed) this.resetLifecycleState();
        await this.initializeLifecycle();
    }

    override async onInitialize(): Promise<void> {
        this.#ensureElements();
    }

    override async onDestroy(): Promise<void> {
        this.#stopTimers();
        this.#releaseCancelButton();
        this.elements = null;
        this.#releaseMaintenance();
    }

    show({ title, seconds, prefixText, suffixText, cancelLabel, onCancel, onComplete }: ShowOptions = {}): void {
        const normalizedSeconds = typeof seconds === 'number' && Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
        this.#ensureElements();
        this.#stopTimers();
        this.#releaseCancelButton();
        this.remainingSeconds = normalizedSeconds;
        this.totalSeconds = normalizedSeconds;
        this.cancelInProgress = false;
        this.cancelHandler = isFunction(onCancel) ? onCancel : null;
        this.completeHandler = isFunction(onComplete) ? onComplete : null;
        this.#activateMaintenance(title || 'countdown');

        const elements = this.elements;
        if (!elements) {
            throw new Error('Countdown elements are not initialized');
        }
        const { overlay, titleNode, prefixNode, suffixNode, valueNode, progressNode, cancelButton } = elements;
        this.lifecycleDom.updateText(titleNode, title ?? '');
        this.lifecycleDom.updateText(prefixNode, prefixText ?? '');
        this.lifecycleDom.updateText(suffixNode, suffixText ?? '');
        this.lifecycleDom.updateText(cancelButton, cancelLabel ?? '');
        cancelButton.disabled = false;

        overlay.classList.remove('u-hidden');
        overlay.classList.add('is-visible');

        this.#updateRemaining(valueNode, progressNode);

        this.cancelButtonDisposer = this.lifecycleResources.addEventListener(cancelButton, 'click', () => terminateHandledPromise(this.#handleCancelClick()));

        if (normalizedSeconds > 0) {
            this.timerHandle = this.lifecycleResources.setTimer(
                () => {
                    this.remainingSeconds -= 1;
                    this.#updateRemaining(valueNode, progressNode);
                    if (this.remainingSeconds <= 0 && !this.cancelInProgress) {
                        this.hide({ canceled: false });
                    }
                },
                1000,
                { repeat: true }
            );
        }
    }

    hide({ canceled }: { canceled?: boolean | undefined } = {}): void {
        this.#stopTimers();
        this.#releaseCancelButton();
        const { overlay } = this.elements ?? {};
        overlay?.classList.remove('is-visible');
        overlay?.classList.add('u-hidden');
        this.elements?.cancelButton.removeAttribute('disabled');

        const callback = canceled ? null : this.completeHandler;
        this.cancelHandler = null;
        this.completeHandler = null;
        this.cancelInProgress = false;
        this.#releaseMaintenance();

        if (callback) {
            callback();
        }
    }

    async #handleCancelClick(): Promise<void> {
        if (this.cancelInProgress) {
            return;
        }
        this.cancelInProgress = true;
        this.elements?.cancelButton.setAttribute('disabled', '');
        let cancelled = false;
        try {
            cancelled = this.cancelHandler ? await this.cancelHandler() : true;
        } catch (error) {
            errorHandler.error(MODULE_ID, 'Countdown cancellation handler failed', ensureError(error));
            cancelled = false;
        }
        if (cancelled) {
            this.hide({ canceled: true });
            return;
        }
        this.cancelInProgress = false;
        if (this.remainingSeconds <= 0) {
            this.hide({ canceled: false });
        } else if (this.elements) {
            this.elements.cancelButton.disabled = false;
        }
    }

    #stopTimers(): void {
        if (this.timerHandle !== null) {
            this.lifecycleResources.clearTimer(this.timerHandle);
            this.timerHandle = null;
        }
    }

    #releaseCancelButton(): void {
        if (this.cancelButtonDisposer) {
            this.cancelButtonDisposer();
            this.cancelButtonDisposer = null;
        }
    }

    #ensureElements(): void {
        if (this.elements?.overlay?.isConnected) {
            return;
        }

        const body = dom.getBody();
        let overlay = this.lifecycleDom.optionalHTMLElement('#countdown-overlay', body);

        if (!overlay) {
            overlay = dom.create('div', {
                id: 'countdown-overlay',
                className: 'restart-overlay hidden'
            });
            const content = dom.create('div', { className: 'restart-content' });
            const icon = dom.create('div', { className: 'restart-icon' });
            dom.appendChild(icon, dom.create('span'));
            const titleNode = dom.create('h2', { className: 'restart-title' });
            const message = dom.create('p', { className: 'restart-message' });
            const prefixNode = dom.create('span', { className: 'countdown-prefix' });
            const valueNode = dom.create('span', { className: 'countdown-value' });
            const suffixNode = dom.create('span', { className: 'countdown-suffix' });
            dom.appendChild(message, [prefixNode, dom.createText(' '), valueNode, dom.createText(' '), suffixNode]);

            const progress = dom.create('div', { className: 'restart-progress progress-bar', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100' });
            const progressNode = dom.create('div', { className: 'restart-progress-bar progress-fill' });
            dom.appendChild(progress, progressNode);

            const cancelButtonNode = dom.create('button', {
                className: 'ui-button countdown-cancel-btn',
                type: 'button'
            });
            if (!(cancelButtonNode instanceof HTMLButtonElement)) {
                throw new Error('Countdown cancel button must be a HTMLButtonElement');
            }
            const cancelButton = cancelButtonNode;

            dom.appendChild(content, [icon, titleNode, message, progress, cancelButton]);
            dom.appendChild(overlay, content);
            dom.appendChild(body, overlay);

            this.elements = {
                overlay,
                titleNode,
                prefixNode,
                suffixNode,
                valueNode,
                progressNode,
                cancelButton
            };
        } else {
            const titleNode = this.lifecycleDom.requireHTMLElement('.restart-title', overlay);
            const prefixNode = this.lifecycleDom.requireHTMLElement('.countdown-prefix', overlay);
            const suffixNode = this.lifecycleDom.requireHTMLElement('.countdown-suffix', overlay);
            const valueNode = this.lifecycleDom.requireHTMLElement('.countdown-value', overlay);
            const progressNode = this.lifecycleDom.requireHTMLElement('.restart-progress-bar', overlay);
            const progressContainer = progressNode.parentElement;
            if (!(progressContainer instanceof HTMLElement)) {
                throw new Error('Countdown progress bar requires a progress container');
            }
            progressContainer.classList.add('restart-progress', 'progress-bar');
            progressContainer.setAttribute('role', 'progressbar');
            progressContainer.setAttribute('aria-valuemin', '0');
            progressContainer.setAttribute('aria-valuemax', '100');
            progressNode.classList.add('restart-progress-bar', 'progress-fill');
            const cancelButtonCandidate = this.lifecycleDom.requireHTMLElement('.countdown-cancel-btn', overlay);
            if (!(cancelButtonCandidate instanceof HTMLButtonElement)) {
                throw new Error('Countdown cancel button must be a HTMLButtonElement');
            }
            const cancelButton = cancelButtonCandidate;

            this.elements = {
                overlay,
                titleNode,
                prefixNode,
                suffixNode,
                valueNode,
                progressNode,
                cancelButton
            };
        }
    }

    #updateRemaining(valueNode: HTMLElement, progressNode: HTMLElement): void {
        this.lifecycleDom.updateText(valueNode, String(Math.max(0, this.remainingSeconds)));
        if (isNumber(this.totalSeconds) && this.totalSeconds > 0) {
            const progress = ((this.totalSeconds - this.remainingSeconds) / this.totalSeconds) * 100;
            this.#syncProgressNode(progressNode, progress);
        } else {
            this.#syncProgressNode(progressNode, 100);
        }
    }

    #syncProgressNode(progressNode: HTMLElement, percent: number): void {
        const progressContainer = progressNode.parentElement;
        if (!(progressContainer instanceof HTMLElement)) {
            throw new Error('Countdown progress bar requires a progress container');
        }
        syncDeterminateProgress({
            fillElement: progressNode,
            progress: percent,
            progressbarElement: progressContainer,
            setStyle: (element, property, value): void => this.lifecycleDom.updateStyle(element, property, value)
        });
    }

    #activateMaintenance(reason: string): void {
        this.#releaseMaintenance();
        this.maintenanceToken = getMaintenanceCoordinator().activate(reason, { mode: 'observe' });
    }

    #releaseMaintenance(): void {
        if (this.maintenanceToken) {
            getMaintenanceCoordinator().deactivate(this.maintenanceToken);
            this.maintenanceToken = null;
        }
    }
}
export { CountdownOverlay, COUNTDOWN_OVERLAY_SERVICE_ID };
