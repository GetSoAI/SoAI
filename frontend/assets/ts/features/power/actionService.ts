/* SoAI - Power confirmation and submission ownership [frontend/assets/ts/features/power/actionService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dismissRestartReminder } from '@core/restartStateService.ts';
import { dismissPersistentNotifications } from '@core/ui/notifications/notifications.ts';
import { buildForceDelayOptions, parseDelayMs } from '@features/power/actionParameters.ts';
import { buildPowerActionDefinitions } from '@features/power/actionDefinitions.ts';
import { shouldClearRestartReminder } from '@features/power/restartReminder.ts';
import type { PowerActionId } from '@features/power/actions.ts';
import type { ActionDefinition, ActionParameters, PowerActionEffects, PowerActionResponse, PowerApi } from '@features/power/contracts.ts';

interface PowerActionDependencies {
    api: PowerApi;
    effects: PowerActionEffects;
    confirm: (action: ActionDefinition, submit: (parameters: ActionParameters) => Promise<void>) => Promise<boolean>;
}

class PowerActionService {
    readonly #dependencies: PowerActionDependencies;
    #operationActive = false;
    #confirmationOpen = false;
    #submitting = false;

    constructor(dependencies: PowerActionDependencies) {
        this.#dependencies = dependencies;
    }

    async executeAction(actionKey: PowerActionId): Promise<void> {
        if (this.#operationActive || this.#confirmationOpen) return;
        const action = buildPowerActionDefinitions().find((definition) => definition.key === actionKey);
        if (!action) throw new Error(`Power action is unavailable: ${actionKey}`);
        this.#confirmationOpen = true;
        try {
            await this.#dependencies.confirm(action, async (parameters): Promise<void> => {
                if (this.#operationActive || this.#submitting) return;
                this.#submitting = true;
                try {
                    const response: PowerActionResponse = await this.#submit(actionKey, parameters);
                    this.#operationActive = true;
                    this.#dependencies.effects.operationAccepted(response);
                    if (shouldClearRestartReminder(actionKey)) {
                        dismissPersistentNotifications([i18n.t('plugins.notifications.restartRequired'), i18n.t('settings.notifications.restartRequired')]);
                        dismissRestartReminder();
                    }
                } finally {
                    this.#submitting = false;
                }
            });
        } finally {
            this.#confirmationOpen = false;
        }
    }

    #submit(action: PowerActionId, parameters: ActionParameters): Promise<PowerActionResponse> {
        const api = this.#dependencies.api;
        switch (action) {
            case 'restartApplication':
                return api.restartApplication({ delay: parseDelayMs(parameters) });
            case 'shutdownApplication':
                return api.shutdownApplication({ delay: parseDelayMs(parameters) });
            case 'rebootSystem':
                return api.reboot(buildForceDelayOptions(parameters));
            case 'shutdownSystem':
                return api.shutdown(buildForceDelayOptions(parameters));
            case 'suspendSystem':
                return api.suspend({ delay: parseDelayMs(parameters) });
            case 'hibernateSystem':
                return api.hibernate({ delay: parseDelayMs(parameters) });
        }
    }

    isOperationActive(): boolean {
        return this.#operationActive;
    }

    isSubmitting(): boolean {
        return this.#submitting;
    }

    setOperationActive(active: boolean): void {
        this.#operationActive = active;
    }
}

export { PowerActionService };
export type { PowerActionDependencies };
