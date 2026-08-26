/* SoAI - Durable power operation UI lifecycle [frontend/assets/ts/pages/power/controllers/powerOperationLifecycleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodePowerOperationResource, type AcceptedPowerActionResponse, type PowerOperationResponse } from '@core/api/contracts/powerContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { POWER_OPERATIONS } from '@core/realtime/streammanager/resources/ids.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CountdownOverlay } from '@features/overlays/public.ts';
import { projectPowerOperationPresentation } from '@pages/power/state/powerOperationState.ts';
import type { PowerApi, PowerOverlayService, RestartOverlayService } from '@pages/power/types.ts';

interface PowerOperationLifecycleDependencies {
    api: () => PowerApi;
    countdownOverlay: CountdownOverlay;
    restartOverlay: RestartOverlayService;
    powerOverlay: PowerOverlayService;
    subscribe: (resource: string, handler: (value: JsonValue | null) => void) => () => void;
    showFeedback: (message: string, type: 'error' | 'success') => void;
    setOperationActive: (active: boolean) => void;
}

const actionTitle = (action: string): string => {
    if (action === 'application_restart') return i18n.t('power.actions.restartApplication.title');
    if (action === 'application_shutdown') return i18n.t('power.actions.shutdownApplication.title');
    if (action === 'host_reboot') return i18n.t('power.actions.rebootSystem.title');
    if (action === 'host_shutdown') return i18n.t('power.actions.shutdownSystem.title');
    if (action === 'host_suspend') return i18n.t('power.actions.suspendSystem.title');
    if (action === 'host_hibernate') return i18n.t('power.actions.hibernateSystem.title');
    return i18n.t('power.actions.restartApplication.title');
};

class PowerOperationLifecycle {
    readonly #dependencies: PowerOperationLifecycleDependencies;
    readonly #resources = new ResourceTracker();
    readonly #notifiedOutcomes = new Set<string>();
    #current: PowerOperationResponse | null = null;
    #transitionAction: string | null = null;
    #transitionOperationId: string | null = null;

    constructor(dependencies: PowerOperationLifecycleDependencies) {
        this.#dependencies = dependencies;
    }

    subscribe(): void {
        this.#resources.cleanup();
        this.#resources.track(
            this.#dependencies.subscribe(POWER_OPERATIONS, (value) => {
                try {
                    this.apply(value === null ? null : decodePowerOperationResource(value));
                } catch (error) {
                    errorHandler.warn('PowerOperationLifecycle', 'Power operation lifecycle payload was rejected', ensureError(error));
                }
            })
        );
    }

    cleanup(): void {
        this.#resources.cleanup();
        this.#current = null;
        this.#dependencies.setOperationActive(false);
    }

    operationAccepted(response: AcceptedPowerActionResponse): void {
        this.#dependencies.setOperationActive(true);
        this.#showCountdown(response.operationId, response.action, response.executeAtMs);
        terminateHandledPromise(this.#refresh(response.operationId));
    }

    apply(operation: PowerOperationResponse | null): void {
        this.#current = operation;
        if (operation === null) {
            this.#dependencies.setOperationActive(false);
            this.#dependencies.countdownOverlay.hide({ canceled: true });
            return;
        }
        const presentation = projectPowerOperationPresentation(operation, Date.now());
        const active = operation.status === 'scheduled' || operation.status === 'executing';
        this.#dependencies.setOperationActive(active);
        if (presentation.mode === 'countdown') {
            this.#showCountdown(operation.operationId, operation.action, operation.executeAtMs);
            return;
        }
        if (presentation.mode === 'transition') {
            this.#showTransition(operation.operationId, operation.action);
            return;
        }
        if (presentation.mode === 'completed') {
            this.#showTransition(operation.operationId, operation.action);
            return;
        }
        this.#dependencies.countdownOverlay.hide({ canceled: true });
        this.#closeTransition(operation.operationId);
        if (operation.status === 'cancelled') {
            this.#notifyOnce(operation, i18n.t('power.overlays.countdown.cancelled'), 'success');
            return;
        }
        this.#notifyOnce(operation, i18n.t('power.operations.failed'), 'error');
    }

    #showCountdown(operationId: string, action: string, executeAtMs: number): void {
        const seconds = Math.max(1, Math.ceil((executeAtMs - Date.now()) / 1000));
        this.#dependencies.countdownOverlay.show({
            title: actionTitle(action),
            seconds,
            prefixText: i18n.t('power.overlays.countdown.prefix'),
            suffixText: i18n.t('power.overlays.countdown.suffix'),
            cancelLabel: i18n.t('power.overlays.countdown.cancel'),
            onCancel: () => this.#cancel(operationId),
            onComplete: () => {
                this.#showTransition(operationId, action);
                terminateHandledPromise(this.#refresh(operationId));
            }
        });
    }

    async #cancel(operationId: string): Promise<boolean> {
        try {
            const operation = await this.#dependencies.api().cancel(operationId);
            this.apply(operation);
            return operation.status === 'cancelled';
        } catch (error) {
            errorHandler.warn('PowerOperationLifecycle', 'Power operation cancellation was rejected', ensureError(error));
            await this.#refresh(operationId);
            return this.#current?.status === 'cancelled';
        }
    }

    async #refresh(operationId: string): Promise<void> {
        try {
            this.apply(await this.#dependencies.api().get(operationId));
        } catch (error) {
            errorHandler.warn('PowerOperationLifecycle', 'Power operation reconciliation failed', ensureError(error));
        }
    }

    #showTransition(operationId: string, action: string): void {
        if (this.#transitionOperationId === operationId) {
            return;
        }
        this.#dependencies.countdownOverlay.hide({ canceled: true });
        if (action === 'application_restart') {
            this.#dependencies.restartOverlay.show('restart-application', { observeTransition: true });
            this.#setTransition(operationId, action);
            return;
        }
        if (action === 'host_reboot') {
            this.#dependencies.restartOverlay.show('system-reboot', { observeTransition: true });
            this.#setTransition(operationId, action);
            return;
        }
        const overlayActions: Readonly<Record<string, string>> = {
            'application_shutdown': 'shutdownApplication',
            'host_shutdown': 'shutdownSystem',
            'host_suspend': 'suspendSystem',
            'host_hibernate': 'hibernateSystem'
        };
        const overlayAction = overlayActions[action];
        if (overlayAction) {
            this.#dependencies.powerOverlay.show(overlayAction);
            this.#setTransition(operationId, action);
        }
    }

    #setTransition(operationId: string, action: string): void {
        this.#transitionOperationId = operationId;
        this.#transitionAction = action;
    }

    #closeTransition(operationId?: string): void {
        if (this.#transitionOperationId === null || (operationId !== undefined && this.#transitionOperationId !== operationId)) {
            return;
        }
        const action = this.#transitionAction;
        this.#transitionOperationId = null;
        this.#transitionAction = null;
        if (action === 'application_restart' || action === 'host_reboot') {
            this.#dependencies.restartOverlay.hide();
            return;
        }
        this.#dependencies.powerOverlay.hide();
    }

    #notifyOnce(operation: PowerOperationResponse, message: string, type: 'error' | 'success'): void {
        const key = `${operation.operationId}:${operation.status}`;
        if (this.#notifiedOutcomes.has(key)) {
            return;
        }
        this.#notifiedOutcomes.add(key);
        this.#dependencies.showFeedback(message, type);
    }
}

export { PowerOperationLifecycle };
export type { PowerOperationLifecycleDependencies };
