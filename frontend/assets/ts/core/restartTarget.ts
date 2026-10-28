/* SoAI - Restart requirement target resolution and navigation [frontend/assets/ts/core/restartTarget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { RestartState } from '@core/restartStateGateway.ts';

type RestartTargetAction = 'restartApplication' | 'rebootSystem';

interface RestartTargetRouter {
    navigate: (route: string) => Promise<void>;
    navigateWithQuery: (route: string, query: Record<string, string>) => void;
}

const SYSTEM_RESTART_SOURCE_PREFIX = 'soai_os.';

const resolveRestartTargetAction = (state: RestartState): RestartTargetAction | null => {
    if (!state.required) return null;
    return state.notifications.some((notification) => notification.path !== null && notification.path.startsWith(SYSTEM_RESTART_SOURCE_PREFIX)) ? 'rebootSystem' : 'restartApplication';
};

const navigateToRestartTarget = (router: RestartTargetRouter, state: RestartState): void => {
    const action = resolveRestartTargetAction(state);
    if (action) {
        router.navigateWithQuery('power', { action });
        return;
    }
    terminateHandledPromise(router.navigate('power'));
};

export { navigateToRestartTarget, resolveRestartTargetAction };
export type { RestartTargetRouter };
