/* SoAI - Frontend power search metadata [frontend/assets/ts/features/power/searchMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { PowerActionId } from '@features/power/actions.ts';

interface PowerActionSearchMetadata {
    key: PowerActionId;
    title: string;
    description: string;
    icon: IconName;
    alias: string;
}

const buildPowerActionSearchMetadata = (): readonly PowerActionSearchMetadata[] =>
    Object.freeze([
        {
            key: 'restartApplication',
            title: i18n.t('power.actions.restartApplication.title'),
            description: i18n.t('power.actions.restartApplication.description'),
            icon: 'restart-application',
            alias: 'restart soai application power'
        },
        {
            key: 'shutdownApplication',
            title: i18n.t('power.actions.shutdownApplication.title'),
            description: i18n.t('power.actions.shutdownApplication.description'),
            icon: 'shutdown-application',
            alias: 'shutdown soai application power'
        },
        {
            key: 'rebootSystem',
            title: i18n.t('power.actions.rebootSystem.title'),
            description: i18n.t('power.actions.rebootSystem.description'),
            icon: 'restart',
            alias: 'restart reboot system power'
        },
        {
            key: 'shutdownSystem',
            title: i18n.t('power.actions.shutdownSystem.title'),
            description: i18n.t('power.actions.shutdownSystem.description'),
            icon: 'power',
            alias: 'shutdown system power'
        },
        {
            key: 'suspendSystem',
            title: i18n.t('power.actions.suspendSystem.title'),
            description: i18n.t('power.actions.suspendSystem.description'),
            icon: 'suspend',
            alias: 'sleep suspend system power'
        },
        {
            key: 'hibernateSystem',
            title: i18n.t('power.actions.hibernateSystem.title'),
            description: i18n.t('power.actions.hibernateSystem.description'),
            icon: 'hibernate',
            alias: 'hibernate system power'
        }
    ]);

export { buildPowerActionSearchMetadata };
export type { PowerActionSearchMetadata };
