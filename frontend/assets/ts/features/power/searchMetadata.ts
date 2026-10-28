/* SoAI - Frontend power search metadata [frontend/assets/ts/features/power/searchMetadata.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildPowerActionDefinitions } from '@features/power/actionDefinitions.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { PowerActionId } from '@features/power/actions.ts';

interface PowerActionSearchMetadata {
    key: PowerActionId;
    title: string;
    description: string;
    icon: IconName;
    alias: string;
}

const POWER_SEARCH_ALIASES: Readonly<Record<PowerActionId, string>> = {
    restartApplication: 'restart soai application power',
    shutdownApplication: 'shutdown soai application power',
    rebootSystem: 'restart reboot system power',
    shutdownSystem: 'shutdown system power',
    suspendSystem: 'sleep suspend system power',
    hibernateSystem: 'hibernate system power'
};

const buildPowerActionSearchMetadata = (): readonly PowerActionSearchMetadata[] => Object.freeze(buildPowerActionDefinitions().map((action) => ({ key: action.key, title: action.title, description: action.description, icon: action.icon, alias: POWER_SEARCH_ALIASES[action.key] })));

export { buildPowerActionSearchMetadata };
export type { PowerActionSearchMetadata };
