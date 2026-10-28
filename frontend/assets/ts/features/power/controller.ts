/* SoAI - Immersive power mode controller [frontend/assets/ts/features/power/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { dom } from '@core/dom/dom.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { createElementResolver } from '@core/dom/elementResolver.ts';
import { requireButtonElement } from '@core/dom/typedElements.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { runWithAbortSignalScope } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { DeferredButtonLoading } from '@core/ui/loadingbuttons/deferredLoadingButton.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { PowerActionService } from '@features/power/actionService.ts';
import { isPowerActionId } from '@features/power/actionDefinitions.ts';
import { confirmPowerAction } from '@features/power/confirmation.ts';
import { PowerOperationLifecycle, type PowerOperationLifecycleDependencies } from '@features/power/operationLifecycle.ts';
import { POWER_MODE_MODAL_ID, refreshPowerModeText } from '@features/power/modalDefinitions.ts';
import { PowerModeMotion } from '@features/power/motion.ts';
import { bindPowerModeRestartIndicator } from '@features/power/restartPresentation.ts';

interface PowerModeDependencies extends Omit<PowerOperationLifecycleDependencies, 'setOperationActive' | 'showFeedback' | 'api'> {
    api: ReturnType<PowerOperationLifecycleDependencies['api']>;
    presenter: ModalPresenterApi;
    canAccess: () => boolean;
    getNavigationButton: () => HTMLButtonElement;
}

class PowerModeController {
    readonly #dependencies: PowerModeDependencies;
    readonly #actions: PowerActionService;
    readonly #lifecycle: PowerOperationLifecycle;
    readonly #motion = new PowerModeMotion();
    readonly #loading = new DeferredButtonLoading();
    #session: AbortController | null = null;
    #confirmation: AbortController | null = null;
    #exitPending: Promise<void> | null = null;
    #queuedOpen: { action: string | undefined; signal: AbortSignal | undefined } | null = null;
    #subscribed = false;
    #openingSequence = 0;

    constructor(dependencies: PowerModeDependencies) {
        this.#dependencies = dependencies;
        this.#lifecycle = new PowerOperationLifecycle({
            ...dependencies,
            api: () => dependencies.api,
            showFeedback: (message, type) => showNotification(message, type),
            setOperationActive: (active) => {
                this.#actions.setOperationActive(active);
                if (active && this.#session !== null) this.closePresentation();
            }
        });
        this.#actions = new PowerActionService({
            api: dependencies.api,
            effects: {
                operationAccepted: (response) => {
                    this.closePresentation();
                    this.#lifecycle.operationAccepted(response);
                }
            },
            confirm: async (action, submit) => {
                const session = this.#session;
                if (!session || !dependencies.canAccess()) return false;
                const confirmation = new AbortController();
                this.#confirmation = confirmation;
                try {
                    return await runWithAbortSignalScope([session.signal, confirmation.signal], (signal) => confirmPowerAction(action, submit, signal));
                } finally {
                    if (this.#confirmation === confirmation) this.#confirmation = null;
                }
            }
        });
    }

    async open(action?: string, requestSignal?: AbortSignal): Promise<void> {
        if (requestSignal?.aborted) return;
        const sequence = ++this.#openingSequence;
        this.accessChanged();
        if (!this.#dependencies.canAccess()) return;
        if (getMaintenanceCoordinator().getState().active) return;
        if (this.#actions.isOperationActive()) await this.#lifecycle.reconcile();
        if (requestSignal?.aborted || sequence !== this.#openingSequence || !this.#dependencies.canAccess() || this.#actions.isOperationActive() || getMaintenanceCoordinator().getState().active) return;
        if (this.#exitPending) {
            this.#queuedOpen = { action, signal: requestSignal };
            return;
        }
        const presenter = this.#dependencies.presenter;
        if (presenter.isOpen(POWER_MODE_MODAL_ID)) {
            if (this.#actions.isSubmitting()) return;
            if (action && isPowerActionId(action)) this.#confirmation?.abort();
            this.#focusAction(action);
            return;
        }
        const modal = presenter.requireElement(POWER_MODE_MODAL_ID);
        refreshPowerModeText(modal);
        const resolver = createElementResolver(modal, 'Power mode');
        const back = requireButtonElement(resolver, '#power-mode-back', 'Power Back');
        const navigationButton = this.#dependencies.getNavigationButton();
        const wasInvisible = navigationButton.classList.contains('u-invisible');
        this.#session = new AbortController();
        const signal = this.#session.signal;
        signal.addEventListener(
            'abort',
            () => {
                if (!wasInvisible) dom.removeClass(navigationButton, 'u-invisible');
            },
            { once: true }
        );
        modal.addEventListener(
            'core.modal.beforeClose',
            (event) => {
                event.preventDefault();
                if (!(event instanceof CustomEvent)) return;
                const pending = this.exit();
                if (pending) terminateHandledPromise(pending);
            },
            { signal }
        );
        modal.addEventListener('core.modal.close', this.#releasePresentation, { signal });
        modal.addEventListener(
            'click',
            (event) => {
                if (!(event.target instanceof Element) || !event.target.matches('.power-mode-surface, .power-mode-scroll')) return;
                event.preventDefault();
                presenter.close(POWER_MODE_MODAL_ID, { reason: 'overlay' });
            },
            { signal }
        );
        bindPageActionDispatcher({
            root: modal,
            signal,
            label: 'PowerMode',
            isAction: isPowerActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: ({ action: selected }) => {
                        if (this.#exitPending) return;
                        terminateHandledPromise(this.#actions.executeAction(selected));
                    }
                }
            }
        });
        bindPowerModeRestartIndicator(modal, signal);
        for (const target of dom.resolveAll('[data-power-initial-focus]', modal)) target.removeAttribute('data-power-initial-focus');
        const initial = action && isPowerActionId(action) ? resolver.requireHTMLElement(`[data-action="${action}"]`) : back;
        initial.setAttribute('data-power-initial-focus', '');
        presenter.open(POWER_MODE_MODAL_ID);
        dom.addClass(navigationButton, 'u-invisible');
        dom.flush();
        this.#motion.enter(modal);
        modal.addEventListener(
            'keydown',
            (event) => {
                if (event.key === 'Escape' || event.key === 'Tab') return;
                event.stopPropagation();
            },
            { signal }
        );
        back.focus({ preventScroll: true });
        this.#focusAction(action);
    }

    exit(): Promise<void> | void {
        if (this.#exitPending) return this.#exitPending;
        if (this.#confirmation || this.#actions.isOperationActive()) return;
        const session = this.#session;
        if (!session) return;
        const modal = this.#dependencies.presenter.requireElement(POWER_MODE_MODAL_ID);
        const resolver = createElementResolver(modal, 'Power mode');
        const back = requireButtonElement(resolver, '#power-mode-back', 'Power Back');
        resolver.requireHTMLElement('.modal-content').focus({ preventScroll: true });
        this.#loading.begin(back);
        this.#exitPending = this.#motion
            .exit(modal)
            .then(() => {
                if (this.#session === session) this.#dependencies.presenter.close(POWER_MODE_MODAL_ID, { force: true, reason: 'power-exit' });
            })
            .catch((error) => {
                errorHandler.error('PowerMode', 'Power mode exit failed', ensureError(error));
                if (this.#session === session) this.#motion.enter(modal);
            })
            .finally(async () => {
                this.#loading.settle();
                if (this.#session === session) back.focus({ preventScroll: true });
                this.#exitPending = null;
                const queued = this.#queuedOpen;
                this.#queuedOpen = null;
                if (queued) await this.open(queued.action, queued.signal);
            });
        return this.#exitPending;
    }

    readonly closePresentation = (): void => {
        this.#openingSequence += 1;
        this.#queuedOpen = null;
        this.#confirmation?.abort();
        if (this.#dependencies.presenter.isOpen(POWER_MODE_MODAL_ID)) this.#dependencies.presenter.close(POWER_MODE_MODAL_ID, { force: true, restoreFocus: false, reason: 'presentation-ended' });
        this.#releasePresentation();
    };

    accessChanged(): void {
        if (this.#dependencies.canAccess()) {
            if (!this.#subscribed) {
                this.#lifecycle.subscribe();
                this.#subscribed = true;
            }
        } else {
            this.closePresentation();
            this.#lifecycle.cleanup();
            this.#subscribed = false;
        }
    }

    isSubmitting(): boolean {
        return this.#actions.isSubmitting();
    }

    destroy(): void {
        this.closePresentation();
        this.#lifecycle.cleanup();
        this.#subscribed = false;
    }

    #focusAction(action?: string): void {
        if (!action || !isPowerActionId(action)) return;
        const modal = this.#dependencies.presenter.requireElement(POWER_MODE_MODAL_ID);
        const target = dom.resolve(`[data-action="${action}"]`, modal);
        if (target instanceof HTMLElement) {
            target.focus({ preventScroll: true });
            scrollElementIntoView(target, { behavior: 'instant', block: 'nearest', inline: 'nearest' });
        }
    }

    readonly #releasePresentation = (): void => {
        this.#session?.abort();
        this.#session = null;
        dom.flush();
        this.#motion.stop();
        this.#loading.settle();
    };
}

export { PowerModeController };
export type { PowerModeDependencies };
