/* SoAI - Power page actions [frontend/assets/ts/pages/power/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { i18n } from '@core/i18n/index.ts';
import type { AcceptedPowerActionResponse } from '@core/api/contracts/powerContracts.ts';
import { buildForceDelayOptions, parseDelayMs, parseDelaySeconds } from '@pages/power/adapters/adapters.ts';
import { POWER_ACTION_IDS } from '@features/power/public.ts';
import { CONFIRM_MODAL_VARIANT, UI_WARN } from '@pages/power/contracts/constants.ts';
import type { ActionDefinition, ActionParameters, PowerActionEffects, PowerActionResponse, PowerApi } from '@pages/power/types.ts';

export type PowerActionId = (typeof POWER_ACTION_IDS)[number];
const { guard: isPowerActionId } = createActionIdSet<PowerActionId>(...POWER_ACTION_IDS);

export { isPowerActionId };

export const buildPowerActionDefinitions = (dependencies: { api: PowerApi; effects: PowerActionEffects }): ActionDefinition[] => {
    const { api, effects } = dependencies;
    return [
        {
            key: 'restartApplication',
            title: i18n.t('power.actions.restartApplication.title'),
            description: i18n.t('power.actions.restartApplication.description'),
            icon: 'restart-application',
            tone: 'accent',
            buttonLabel: i18n.t('power.actions.restartApplication.buttonLabel'),
            buttonVariant: 'ui-variant-accent',
            options: [
                {
                    type: 'number',
                    parameter: 'delay',
                    label: i18n.t('power.actions.restartApplication.optionDelay'),
                    defaultValue: 0,
                    min: 0,
                    max: 86400
                }
            ],
            confirm: {
                variant: CONFIRM_MODAL_VARIANT,
                title: i18n.t('power.actions.restartApplication.confirmTitle'),
                warning: i18n.t('power.actions.restartApplication.confirmWarning'),
                message: i18n.t('power.actions.restartApplication.confirmMessage')
            },
            run: (parameters: ActionParameters): Promise<AcceptedPowerActionResponse> => api.restartApplication({ delay: parseDelayMs(parameters) }),
            successNotification: (): { message: string; type: string } => ({ message: i18n.t('power.actions.restartApplication.successNotification'), type: 'success' }),
            errorToastMessage: null,
            onSuccess: (_parameters: ActionParameters, result: PowerActionResponse): void => effects.operationAccepted(result)
        },
        {
            key: 'shutdownApplication',
            title: i18n.t('power.actions.shutdownApplication.title'),
            description: i18n.t('power.actions.shutdownApplication.description'),
            icon: 'shutdown-application',
            tone: 'application-shutdown',
            buttonLabel: i18n.t('power.actions.shutdownApplication.buttonLabel'),
            buttonVariant: 'ui-variant-shutdown',
            options: [
                {
                    type: 'number',
                    parameter: 'delay',
                    label: i18n.t('power.actions.shutdownApplication.optionDelay'),
                    defaultValue: 10,
                    min: 0,
                    max: 86400
                }
            ],
            confirm: {
                variant: 'danger',
                title: i18n.t('power.actions.shutdownApplication.confirmTitle'),
                warning: i18n.t('power.actions.shutdownApplication.confirmWarning'),
                getMessage: (parameters: ActionParameters): string => {
                    const delay = parseDelaySeconds(parameters);
                    return delay > 0 ? i18n.t('power.actions.shutdownApplication.confirmMessageWithDelay', { delay }) : i18n.t('power.actions.shutdownApplication.confirmMessage');
                }
            },
            run: (parameters: ActionParameters): Promise<AcceptedPowerActionResponse> => api.shutdownApplication({ delay: parseDelayMs(parameters) }),
            successNotification: (parameters: ActionParameters): { message: string; type: string } => {
                const delay = parseDelaySeconds(parameters);
                const message = delay > 0 ? i18n.t('power.actions.shutdownApplication.successNotificationWithDelay', { delay }) : i18n.t('power.actions.shutdownApplication.successNotification');
                return { message, type: UI_WARN };
            },
            errorToastMessage: null,
            onSuccess: (_parameters: ActionParameters, result: PowerActionResponse): void => effects.operationAccepted(result)
        },
        {
            key: 'rebootSystem',
            title: i18n.t('power.actions.rebootSystem.title'),
            description: i18n.t('power.actions.rebootSystem.description'),
            icon: 'restart',
            tone: UI_WARN,
            buttonLabel: i18n.t('power.actions.rebootSystem.buttonLabel'),
            buttonVariant: `ui-variant-${UI_WARN}`,
            options: [
                {
                    type: 'checkbox',
                    parameter: 'force',
                    label: i18n.t('power.actions.rebootSystem.optionForce'),
                    defaultValue: false
                },
                {
                    type: 'number',
                    parameter: 'delay',
                    label: i18n.t('power.actions.rebootSystem.optionDelay'),
                    defaultValue: 10,
                    min: 0,
                    max: 86400
                }
            ],
            confirm: {
                variant: 'danger',
                title: i18n.t('power.actions.rebootSystem.confirmTitle'),
                warning: i18n.t('power.actions.rebootSystem.confirmWarning'),
                getMessage: (parameters: ActionParameters): string => {
                    const delay = parseDelaySeconds(parameters);
                    return delay > 0 ? i18n.t('power.actions.rebootSystem.confirmMessageWithDelay', { delay }) : i18n.t('power.actions.rebootSystem.confirmMessage');
                }
            },
            run: (parameters: ActionParameters): Promise<AcceptedPowerActionResponse> => api.reboot(buildForceDelayOptions(parameters)),
            successNotification: (parameters: ActionParameters): { message: string; type: string } => {
                const delay = parseDelaySeconds(parameters);
                const message = delay > 0 ? i18n.t('power.actions.rebootSystem.successNotificationWithDelay', { delay }) : i18n.t('power.actions.rebootSystem.successNotification');
                return { message, type: UI_WARN };
            },
            errorToastMessage: null,
            onSuccess: (_parameters: ActionParameters, result: PowerActionResponse): void => effects.operationAccepted(result)
        },
        {
            key: 'shutdownSystem',
            title: i18n.t('power.actions.shutdownSystem.title'),
            description: i18n.t('power.actions.shutdownSystem.description'),
            icon: 'power',
            tone: 'danger',
            buttonLabel: i18n.t('power.actions.shutdownSystem.buttonLabel'),
            buttonVariant: 'ui-variant-danger',
            options: [
                {
                    type: 'checkbox',
                    parameter: 'force',
                    label: i18n.t('power.actions.shutdownSystem.optionForce'),
                    defaultValue: false
                },
                {
                    type: 'number',
                    parameter: 'delay',
                    label: i18n.t('power.actions.shutdownSystem.optionDelay'),
                    defaultValue: 10,
                    min: 0,
                    max: 86400
                }
            ],
            confirm: {
                variant: 'danger',
                title: i18n.t('power.actions.shutdownSystem.confirmTitle'),
                warning: i18n.t('power.actions.shutdownSystem.confirmWarning'),
                getMessage: (parameters: ActionParameters): string => {
                    const delay = parseDelaySeconds(parameters);
                    return delay > 0 ? i18n.t('power.actions.shutdownSystem.confirmMessageWithDelay', { delay }) : i18n.t('power.actions.shutdownSystem.confirmMessage');
                }
            },
            run: (parameters: ActionParameters): Promise<AcceptedPowerActionResponse> => api.shutdown(buildForceDelayOptions(parameters)),
            successNotification: (parameters: ActionParameters): { message: string; type: string } => {
                const delay = parseDelaySeconds(parameters);
                const message = delay > 0 ? i18n.t('power.actions.shutdownSystem.successNotificationWithDelay', { delay }) : i18n.t('power.actions.shutdownSystem.successNotification');
                return { message, type: UI_WARN };
            },
            errorToastMessage: null,
            onSuccess: (_parameters: ActionParameters, result: PowerActionResponse): void => effects.operationAccepted(result)
        },
        {
            key: 'suspendSystem',
            title: i18n.t('power.actions.suspendSystem.title'),
            description: i18n.t('power.actions.suspendSystem.description'),
            icon: 'suspend',
            tone: UI_WARN,
            buttonLabel: i18n.t('power.actions.suspendSystem.buttonLabel'),
            buttonVariant: `ui-variant-${UI_WARN}`,
            options: [
                {
                    type: 'number',
                    parameter: 'delay',
                    label: i18n.t('power.actions.suspendSystem.optionDelay'),
                    defaultValue: 10,
                    min: 0,
                    max: 86400
                }
            ],
            confirm: {
                variant: CONFIRM_MODAL_VARIANT,
                title: i18n.t('power.actions.suspendSystem.confirmTitle'),
                warning: i18n.t('power.actions.suspendSystem.confirmWarning'),
                getMessage: (parameters: ActionParameters): string => {
                    const delay = parseDelaySeconds(parameters);
                    return delay > 0 ? i18n.t('power.actions.suspendSystem.confirmMessageWithDelay', { delay }) : i18n.t('power.actions.suspendSystem.confirmMessage');
                }
            },
            run: (parameters: ActionParameters): Promise<AcceptedPowerActionResponse> => api.suspend({ delay: parseDelayMs(parameters) }),
            successNotification: (parameters: ActionParameters): { message: string; type: string } => {
                const delay = parseDelaySeconds(parameters);
                const message = delay > 0 ? i18n.t('power.actions.suspendSystem.successNotificationWithDelay', { delay }) : i18n.t('power.actions.suspendSystem.successNotification');
                return { message, type: UI_WARN };
            },
            errorToastMessage: null,
            onSuccess: (_parameters: ActionParameters, result: PowerActionResponse): void => effects.operationAccepted(result)
        },
        {
            key: 'hibernateSystem',
            title: i18n.t('power.actions.hibernateSystem.title'),
            description: i18n.t('power.actions.hibernateSystem.description'),
            icon: 'hibernate',
            tone: 'status-blue',
            buttonLabel: i18n.t('power.actions.hibernateSystem.buttonLabel'),
            buttonVariant: 'ui-variant-primary',
            options: [
                {
                    type: 'number',
                    parameter: 'delay',
                    label: i18n.t('power.actions.hibernateSystem.optionDelay'),
                    defaultValue: 10,
                    min: 0,
                    max: 86400
                }
            ],
            confirm: {
                variant: CONFIRM_MODAL_VARIANT,
                title: i18n.t('power.actions.hibernateSystem.confirmTitle'),
                warning: i18n.t('power.actions.hibernateSystem.confirmWarning'),
                getMessage: (parameters: ActionParameters): string => {
                    const delay = parseDelaySeconds(parameters);
                    return delay > 0 ? i18n.t('power.actions.hibernateSystem.confirmMessageWithDelay', { delay }) : i18n.t('power.actions.hibernateSystem.confirmMessage');
                }
            },
            run: (parameters: ActionParameters): Promise<AcceptedPowerActionResponse> => api.hibernate({ delay: parseDelayMs(parameters) }),
            successNotification: (parameters: ActionParameters): { message: string; type: string } => {
                const delay = parseDelaySeconds(parameters);
                const message = delay > 0 ? i18n.t('power.actions.hibernateSystem.successNotificationWithDelay', { delay }) : i18n.t('power.actions.hibernateSystem.successNotification');
                return { message, type: 'info' };
            },
            errorToastMessage: null,
            onSuccess: (_parameters: ActionParameters, result: PowerActionResponse): void => effects.operationAccepted(result)
        }
    ];
};
