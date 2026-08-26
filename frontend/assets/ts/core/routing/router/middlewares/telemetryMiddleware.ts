/* SoAI - Shared routing telemetry middleware [frontend/assets/ts/core/routing/router/middlewares/telemetryMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { NavigationResultType } from '@core/navigationMiddleware.ts';
import { normalizeMiddlewareOutcome, readErrorMessage } from '@core/routing/router/navigationMiddlewareNormalization.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type RouterMiddleware = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType>;

const createTelemetryNavigationMiddleware = (emitRouterEvent: (stage: string, data?: Record<string, JsonValue | null | undefined>, severity?: string) => void): RouterMiddleware => {
    return async (context: NavigationContext, next: () => Promise<NavigationResultType>): Promise<NavigationResultType> => {
        const data = {
            component: context.route.component || null,
            path: context.request.path || null,
            source: context.meta['source'] ?? null
        };
        emitRouterEvent('navigation:middleware:start', data);
        const start = Date.now();
        try {
            const result = await next();
            const outcome = normalizeMiddlewareOutcome(result);
            emitRouterEvent('navigation:middleware:complete', {
                ...data,
                status: outcome.status,
                duration: Date.now() - start
            });
            return outcome;
        } catch (error) {
            const runtimeError = ensureError(error);
            emitRouterEvent('navigation:middleware:error', { ...data, message: readErrorMessage(runtimeError) }, 'error');
            throw runtimeError;
        }
    };
};

export { createTelemetryNavigationMiddleware };
