/* SoAI - Power action catalog [frontend/assets/ts/features/power/actionDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createActionIdSet } from '@core/dom/actions/actionIdGuard.ts';
import { i18n } from '@core/i18n/index.ts';
import { POWER_ACTION_IDS, type PowerActionId } from '@features/power/actions.ts';
import type { ActionDefinition } from '@features/power/contracts.ts';

const { guard: isPowerActionId } = createActionIdSet<PowerActionId>(...POWER_ACTION_IDS);

export { isPowerActionId };

export const buildPowerActionDefinitions = (): ActionDefinition[] => {
    return [
        {
            key: 'restartApplication',
            title: i18n.t('power.actions.restartApplication.title'),
            description: i18n.t('power.actions.restartApplication.description'),
            icon: 'restart-application',
            buttonLabel: i18n.t('power.actions.restartApplication.buttonLabel'),
            variant: 'warning',
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
                title: i18n.t('power.actions.restartApplication.confirmTitle'),
                message: i18n.t('power.actions.restartApplication.confirmMessage'),
                warning: i18n.t('power.actions.restartApplication.confirmWarning'),
                icon: 'restart-application-modal'
            }
        },
        {
            key: 'shutdownApplication',
            title: i18n.t('power.actions.shutdownApplication.title'),
            description: i18n.t('power.actions.shutdownApplication.description'),
            icon: 'shutdown-application',
            buttonLabel: i18n.t('power.actions.shutdownApplication.buttonLabel'),
            variant: 'danger',
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
                title: i18n.t('power.actions.shutdownApplication.confirmTitle'),
                message: i18n.t('power.actions.shutdownApplication.confirmMessage'),
                warning: i18n.t('power.actions.shutdownApplication.confirmWarning'),
                icon: 'shutdown-application-modal'
            }
        },
        {
            key: 'rebootSystem',
            title: i18n.t('power.actions.rebootSystem.title'),
            description: i18n.t('power.actions.rebootSystem.description'),
            icon: 'restart',
            buttonLabel: i18n.t('power.actions.rebootSystem.buttonLabel'),
            variant: 'warning',
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
                title: i18n.t('power.actions.rebootSystem.confirmTitle'),
                message: i18n.t('power.actions.rebootSystem.confirmMessage'),
                warning: i18n.t('power.actions.rebootSystem.confirmWarning'),
                icon: 'restart-modal'
            }
        },
        {
            key: 'shutdownSystem',
            title: i18n.t('power.actions.shutdownSystem.title'),
            description: i18n.t('power.actions.shutdownSystem.description'),
            icon: 'power',
            buttonLabel: i18n.t('power.actions.shutdownSystem.buttonLabel'),
            variant: 'danger',
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
                title: i18n.t('power.actions.shutdownSystem.confirmTitle'),
                message: i18n.t('power.actions.shutdownSystem.confirmMessage'),
                warning: i18n.t('power.actions.shutdownSystem.confirmWarning'),
                icon: 'power-modal'
            }
        },
        {
            key: 'suspendSystem',
            title: i18n.t('power.actions.suspendSystem.title'),
            description: i18n.t('power.actions.suspendSystem.description'),
            icon: 'suspend',
            buttonLabel: i18n.t('power.actions.suspendSystem.buttonLabel'),
            variant: 'warning',
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
                title: i18n.t('power.actions.suspendSystem.confirmTitle'),
                message: i18n.t('power.actions.suspendSystem.confirmMessage'),
                warning: i18n.t('power.actions.suspendSystem.confirmWarning'),
                icon: 'suspend-modal'
            }
        },
        {
            key: 'hibernateSystem',
            title: i18n.t('power.actions.hibernateSystem.title'),
            description: i18n.t('power.actions.hibernateSystem.description'),
            icon: 'hibernate',
            buttonLabel: i18n.t('power.actions.hibernateSystem.buttonLabel'),
            variant: 'primary',
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
                title: i18n.t('power.actions.hibernateSystem.confirmTitle'),
                message: i18n.t('power.actions.hibernateSystem.confirmMessage'),
                warning: i18n.t('power.actions.hibernateSystem.confirmWarning'),
                icon: 'hibernate-modal'
            }
        }
    ];
};
