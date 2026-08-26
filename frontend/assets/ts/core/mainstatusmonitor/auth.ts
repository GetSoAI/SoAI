/* SoAI - Shared main status monitor auth [frontend/assets/ts/core/mainstatusmonitor/auth.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAuthManager } from '@core/auth/public.ts';
import { isAuthManager } from '@core/mainstatusmonitor/guards.ts';
import type { AuthManagerInterface } from '@core/mainstatusmonitor/types.ts';

const requireMainStatusAuthManager = (): AuthManagerInterface => {
    const authManager = getAuthManager();
    if (!isAuthManager(authManager)) {
        throw new Error('Auth manager is unavailable');
    }
    return authManager;
};

export { requireMainStatusAuthManager };
