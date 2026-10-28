/* SoAI - Durable power operation UI lifecycle [frontend/assets/ts/features/power/operationLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodePowerOperationResource, type AcceptedPowerActionResponse, type PowerOperationResponse } from '@core/api/contracts/powerContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { i18n } from '@core/i18n/index.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { POWER_OPERATIONS } from '@core/realtime/streammanager/resources/ids.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { projectPowerOperationPresentation } from '@features/power/operationState.ts';
import type { CountdownPresentation, PowerApi, PowerOverlayService, RestartOverlayService } from '@features/power/contracts.ts';

interface PowerOperationLifecycleDependencies {
    api: () => PowerApi;
    countdownOverlay: CountdownPresentation;
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
    #acceptedOperationId: string | null = null;
    #revision = 0;
    #countdown: { operationId: string; executeAtMs: number } | null = null;
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
        this.#acceptedOperationId = null;
        this.#revision += 1;
        this.#dependencies.setOperationActive(false);
    }

    operationAccepted(response: AcceptedPowerActionResponse): void {
        if (this.#current?.operationId === response.operationId) {
            this.apply(this.#current);
            return;
        }
        this.#current = null;
        this.#acceptedOperationId = response.operationId;
        this.#revision += 1;
        this.#dependencies.setOperationActive(true);
        this.#showCountdown(response.operationId, response.action, response.executeAtMs);
        terminateHandledPromise(this.#refresh(response.operationId));
    }

    apply(operation: PowerOperationResponse | null): void {
        if (operation === null && this.#acceptedOperationId !== null) {
            terminateHandledPromise(this.#refresh(this.#acceptedOperationId));
            return;
        }
        const current = this.#current;
        if (current?.operationId === operation?.operationId && current !== null && operation !== null) {
            const currentTerminal = current.status === 'cancelled' || current.status === 'failed' || current.status === 'completed';
            if (currentTerminal && operation.status !== current.status) return;
            if (current.status === 'executing' && operation.status === 'scheduled') return;
        }
        this.#revision += 1;
        this.#current = operation;
        if (operation === null) {
            this.#countdown = null;
            this.#dependencies.setOperationActive(false);
            this.#dependencies.countdownOverlay.hide({ canceled: true });
            return;
        }
        const presentation = projectPowerOperationPresentation(operation, serverEpochMs());
        const active = operation.status === 'scheduled' || operation.status === 'executing';
        this.#acceptedOperationId = active ? operation.operationId : null;
        this.#dependencies.setOperationActive(active);
        if (presentation.mode === 'countdown') {
            this.#showCountdown(operation.operationId, operation.action, operation.executeAtMs);
            return;
        }
        if (presentation.mode === 'transition' || presentation.mode === 'completed') {
            this.#showTransition(operation.operationId, operation.action);
            return;
        }
        this.#acceptedOperationId = null;
        this.#countdown = null;
        this.#dependencies.countdownOverlay.hide({ canceled: true });
        this.#closeTransition(operation.operationId);
        if (operation.status === 'cancelled') {
            this.#notifyOnce(operation, i18n.t('power.overlays.countdown.cancelled'), 'success');
            return;
        }
        this.#notifyOnce(operation, i18n.t('power.operations.failed'), 'error');
    }

    #showCountdown(operationId: string, action: string, executeAtMs: number): void {
        if (this.#transitionOperationId !== null && this.#transitionOperationId !== operationId) this.#closeTransition();
        if (this.#countdown?.operationId === operationId && this.#countdown.executeAtMs === executeAtMs) return;
        this.#countdown = { operationId, executeAtMs };
        this.#dependencies.countdownOverlay.show({
            title: actionTitle(action),
            executeAtMs,
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

    #ownsOperation(operationId: string): boolean {
        return this.#current?.operationId === operationId || this.#acceptedOperationId === operationId;
    }

    async #cancel(operationId: string): Promise<boolean> {
        try {
            const operation = await this.#dependencies.api().cancel(operationId);
            if (this.#ownsOperation(operationId)) this.apply(operation);
            return operation.status === 'cancelled';
        } catch (error) {
            showOperationFailureNotification({ error: ensureError(error), rawMessage: false, showNotification: (message) => this.#dependencies.showFeedback(message, 'error') });
            if (this.#ownsOperation(operationId)) await this.#refresh(operationId);
            return this.#current?.operationId === operationId && this.#current.status === 'cancelled';
        }
    }

    async reconcile(): Promise<void> {
        const operationId = this.#acceptedOperationId;
        if (operationId !== null) await this.#refresh(operationId, true);
    }

    async #refresh(operationId: string, notifyFailure = false): Promise<void> {
        const revision = this.#revision;
        try {
            const operation = await this.#dependencies.api().get(operationId);
            if (revision === this.#revision || this.#current?.operationId === operation.operationId) this.apply(operation);
        } catch (error) {
            errorHandler.warn('PowerOperationLifecycle', 'Power operation reconciliation failed', ensureError(error));
            if (notifyFailure) showOperationFailureNotification({ error: ensureError(error), rawMessage: false, showNotification: (message) => this.#dependencies.showFeedback(message, 'error') });
        }
    }

    #showTransition(operationId: string, action: string): void {
        this.#countdown = null;
        if (this.#transitionOperationId === operationId) {
            return;
        }
        this.#closeTransition();
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
