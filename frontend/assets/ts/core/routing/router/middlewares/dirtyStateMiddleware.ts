/* SoAI - Shared routing dirty state middleware [frontend/assets/ts/core/routing/router/middlewares/dirtyStateMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { NAVIGATION_STATUS, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { evaluateDirtyStateGuards } from '@core/navigationGuards.ts';
import { normalizeMiddlewareOutcome } from '@core/routing/router/navigationMiddlewareNormalization.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

const createDirtyStateNavigationMiddleware = (): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        const verdict = await evaluateDirtyStateGuards(context);
        const outcome = normalizeMiddlewareOutcome(verdict);
        if (outcome.status !== NAVIGATION_STATUS.CONTINUE) {
            return outcome;
        }
        return next();
    };
};

export { createDirtyStateNavigationMiddleware };
