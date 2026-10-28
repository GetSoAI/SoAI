/* SoAI - Restart notification Power shortcut [frontend/assets/ts/core/restartNotificationAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getRestartState } from '@core/restartStateService.ts';
import { navigateToRestartTarget } from '@core/restartTarget.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import type { NotificationButton } from '@core/ui/notifications/types.ts';

const createRestartNotificationButton = (text: string): NotificationButton => ({
    text,
    variant: 'warning',
    icon: 'restart',
    action: () => {
        navigateToRestartTarget(requireRouter(), getRestartState());
        return false;
    }
});

export { createRestartNotificationButton };
