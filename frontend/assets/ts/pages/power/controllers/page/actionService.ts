/* SoAI - Power page action service [frontend/assets/ts/pages/power/controllers/page/actionService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readFiniteInputValueOrNull } from '@core/dom/formValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { resetRestartState } from '@core/restartStateService.ts';
import { dismissPersistentNotifications } from '@core/ui/notifications/notifications.ts';
import { buildPowerActionDefinitions } from '@pages/power/actions.ts';
import type { PowerActionId } from '@features/power/public.ts';
import { shouldClearRestartReminder } from '@pages/power/controllers/powerRestartReminder.ts';
import type { ActionDefinition, ActionParameters, ConfirmActionOptions, PowerActionEffects, PowerApi } from '@pages/power/types.ts';

type ActionMap = Map<PowerActionId, ActionDefinition>;

interface PowerPageActionHost {
    getOptionId: (actionKey: PowerActionId, optionParameter: keyof ActionParameters) => string;
    optionalOptionInput: (selectorOrId: string) => HTMLInputElement | null;
}

interface PowerPageActionDependencies {
    getPowerApi: () => PowerApi;
    effects: PowerActionEffects;
    host: PowerPageActionHost;
    confirmAction: (options: ConfirmActionOptions) => Promise<boolean>;
}

class PowerPageActionService {
    readonly #dependencies: PowerPageActionDependencies;
    #actionMap: ActionMap = new Map();
    #operationActive = false;
    #submissionInProgress = false;

    constructor(dependencies: PowerPageActionDependencies) {
        this.#dependencies = dependencies;
    }

    buildActionDefinitions(): ActionDefinition[] {
        const api = this.#dependencies.getPowerApi();
        const definitions = buildPowerActionDefinitions({
            api,
            effects: this.#dependencies.effects
        });
        this.#actionMap = new Map(definitions.map((definition) => [definition.key, definition]));
        return definitions;
    }

    async executeAction(actionKey: PowerActionId): Promise<void> {
        if (this.#operationActive || this.#submissionInProgress) {
            return;
        }
        const action = this.#actionMap.get(actionKey);
        if (!action) {
            return;
        }

        const parameters = this.#collectActionParameters(action);
        const clearRestartReminder = shouldClearRestartReminder(actionKey);

        const message = action.confirm ? this.#resolveMessage(action.confirm, parameters) : undefined;
        const successDescriptor = action.successNotification ? action.successNotification(parameters) : null;
        const onSuccess = action.onSuccess;

        this.#submissionInProgress = true;
        let ok = false;
        try {
            ok = await this.#dependencies.confirmAction({
                title: action.confirm?.title ?? action.title,
                message,
                warning: action.confirm?.warning,
                variant: action.confirm?.variant ?? 'warning',
                icon: action.icon,
                run: async () => {
                    if (clearRestartReminder) {
                        dismissPersistentNotifications([i18n.t('plugins.notifications.restartRequired'), i18n.t('settings.notifications.restartRequired')]);
                    }
                    return action.run(parameters);
                },
                successMessage: successDescriptor?.message,
                errorToastMessage: action.errorToastMessage ?? undefined,
                onSuccess: onSuccess ? (result) => onSuccess(parameters, result) : undefined
            });
        } finally {
            this.#submissionInProgress = false;
        }

        if (ok && clearRestartReminder) {
            resetRestartState();
        }
    }

    setOperationActive(active: boolean): void {
        this.#operationActive = active;
    }

    #resolveMessage(confirm: ActionDefinition['confirm'], parameters: ActionParameters): string | undefined {
        if (!confirm) {
            return undefined;
        }

        if (confirm.getMessage) {
            return confirm.getMessage(parameters);
        }

        return confirm.message;
    }

    #collectActionParameters(action: ActionDefinition): ActionParameters {
        if (!action.options || action.options.length === 0) {
            return {};
        }

        const parameters: ActionParameters = {};

        for (const option of action.options) {
            const elementId = this.#dependencies.host.getOptionId(action.key, option.parameter);
            const element = this.#dependencies.host.optionalOptionInput(elementId);

            if (!element) {
                if (option.parameter === 'force') {
                    parameters.force = typeof option.defaultValue === 'boolean' ? option.defaultValue : false;
                } else if (option.parameter === 'delay') {
                    parameters.delay = typeof option.defaultValue === 'number' && Number.isFinite(option.defaultValue) ? option.defaultValue : 0;
                }
                continue;
            }

            if (element.closest('.u-hidden')) {
                if (option.parameter === 'force') {
                    parameters.force = false;
                } else if (option.parameter === 'delay') {
                    parameters.delay = 0;
                }
                continue;
            }

            if (option.type === 'checkbox') {
                if (option.parameter !== 'force') {
                    throw new Error('Power checkbox option param must be "force"');
                }
                parameters.force = element.checked;
                continue;
            }

            if (option.type === 'number') {
                if (option.parameter !== 'delay') {
                    throw new Error('Power number option param must be "delay"');
                }
                parameters.delay = readFiniteInputValueOrNull(element) ?? 0;
                continue;
            }

            if (option.parameter === 'force') {
                parameters.force = element.value === 'true';
            }
        }

        return parameters;
    }
}

export { PowerPageActionService };
export type { PowerPageActionHost };
