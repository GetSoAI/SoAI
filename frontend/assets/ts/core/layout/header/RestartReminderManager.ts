/* SoAI - Shared layout restart reminder manager [frontend/assets/ts/core/layout/header/RestartReminderManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { HEADER_ACTION_IDS } from '@core/headeractions/constants.ts';
import type { HeaderServiceResolver } from '@core/layout/HeaderInterface.ts';
import { getRestartStateService } from '@core/restartStateService.ts';
import type { RestartState } from '@core/restartStateGateway.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

export interface RestartReminderHost {
    resolveService: HeaderServiceResolver;
}

interface NormalizedNotification {
    reason: string;
    path: string | null;
}

interface NormalizedState {
    required: boolean;
    reasons: string[];
    notifications: NormalizedNotification[];
}

interface RestartReminderManagerOptions {
    header: RestartReminderHost;
}

interface RouterInterface {
    navigate: (route: string) => Promise<void>;
}

const isRouterInterface = <T>(value: T): value is T & RouterInterface => isObject(value) && 'navigate' in value && isFunction(value.navigate);

export class RestartReminderManager {
    header: RestartReminderHost;
    unsubscribeRestart: (() => void) | null = null;
    lastStateJson: string | null = null;
    lastState: NormalizedState | null = null;
    actionContextId: string = HEADER_ACTION_IDS.restartReminder;
    actionController: HeaderActionController | null = null;
    destroyed: boolean = false;
    handleActionInvoke: () => void;

    constructor({ header }: RestartReminderManagerOptions) {
        this.header = header;
        this.unsubscribeRestart = null;
        this.lastStateJson = null;
        this.lastState = null;
        this.actionContextId = HEADER_ACTION_IDS.restartReminder;
        this.actionController = null;
        this.destroyed = false;
        this.handleActionInvoke = (): void => {
            const router = this.header.resolveService('core.router', isRouterInterface, 'Router');
            terminateHandledPromise(router.navigate('power'));
        };
    }

    async initialize(): Promise<void> {
        this.destroyed = false;
        this.ensureActionController();
        const restartStateService = getRestartStateService();
        this.unsubscribeRestart = restartStateService.subscribe((state) => this.handleState(state), {
            immediate: true
        });
    }

    destroy(): void {
        this.destroyed = true;
        if (isFunction(this.unsubscribeRestart)) {
            this.unsubscribeRestart();
        }
        this.unsubscribeRestart = null;
        this.lastStateJson = null;
        this.lastState = null;
        if (this.actionController && isFunction(this.actionController.dispose)) {
            this.actionController.dispose();
        }
        this.actionController = null;
    }

    localize(): void {
        if (!this.lastState) {
            return;
        }
        this.applyState(this.lastState);
    }

    handleState(state: RestartState): void {
        const reasons = state.reasons.map((item) => String(item ?? '').trim()).filter(Boolean);
        const notifications = state.notifications
            .map((item) => ({
                reason: item.reason.trim(),
                path: item.path?.trim() || null
            }))
            .filter((item) => item.reason.length);
        const required = Boolean(state.required);
        const normalized: NormalizedState = { required, reasons, notifications };
        const json = JSON.stringify(normalized);
        if (json === this.lastStateJson) {
            return;
        }
        this.lastStateJson = json;
        this.lastState = normalized;
        this.applyState(normalized);
    }

    applyState(normalized: NormalizedState): void {
        this.lastState = normalized;
        const hasReminder = normalized.required;
        this.invokeWithController((controller) => {
            if (hasReminder) {
                controller.show({
                    onClick: this.handleActionInvoke,
                    order: 30
                });
                return;
            }
            controller.hide();
        });
    }

    ensureActionController(): HeaderActionController {
        if (!this.actionController) {
            this.actionController = createHeaderActionController({
                actionId: HEADER_ACTION_IDS.restartReminder,
                contextId: this.actionContextId
            });
        }
        return this.actionController;
    }

    invokeWithController(callback: (controller: HeaderActionController) => void): void {
        if (!isFunction(callback)) {
            return;
        }
        const controller = this.ensureActionController();
        try {
            callback(controller);
        } catch (error) {
            if (error instanceof Error && error.message && error.message.includes('has been disposed')) {
                this.actionController = null;
                callback(this.ensureActionController());
                return;
            }
            throw error;
        }
    }
}
