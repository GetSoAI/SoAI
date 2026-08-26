/* SoAI - Shared frontend navigation middleware [frontend/assets/ts/core/navigationMiddleware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getPerformance } from '@core/environment/public.ts';
import { ErrorBoundary } from '@core/ErrorBoundary.ts';
import { telemetry } from '@core/telemetry/service.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isBoolean, isFunction, isObject, isString } from '@core/typeGuards.ts';
import { coerceErrorMessage, ensureError } from '@core/errors/coerce.ts';
import type { NavigationContext, NavigationOptions } from '@core/routing/router/types.ts';

interface NavigationStatus {
    CONTINUE: 'continue';
    BLOCKED: 'blocked';
    REDIRECT: 'redirect';
}

interface NavigationResultContinue {
    status: 'continue';
    detail: JsonValue;
}

interface NavigationResultBlocked {
    status: 'blocked';
    reason: string | null;
}

interface NavigationResultRedirect {
    status: 'redirect';
    target: string;
    options: NavigationOptions;
}

type NavigationResultType = NavigationResultContinue | NavigationResultBlocked | NavigationResultRedirect;

type MiddlewareHandler = (context: NavigationContext, next: () => Promise<NavigationResultType>) => Promise<NavigationResultType | boolean | void | null> | NavigationResultType | boolean | void | null;

interface MiddlewareOptions {
    priority?: number;
    name?: string;
}

interface MiddlewareEntry {
    id: symbol;
    handler: MiddlewareHandler;
    priority: number;
    name: string;
}

interface NavigationMiddlewareController {
    use: (middleware: MiddlewareHandler, options?: MiddlewareOptions) => () => void;
    run: (context: NavigationContext) => Promise<NavigationResultType>;
    clear: () => void;
    size: () => number;
}

const NAVIGATION_STATUS: NavigationStatus = Object.freeze({
    CONTINUE: 'continue',
    BLOCKED: 'blocked',
    REDIRECT: 'redirect'
});

const navigationResult = Object.freeze({
    continue: (detail: JsonValue = null): NavigationResultContinue => ({
        status: NAVIGATION_STATUS.CONTINUE,
        detail
    }),
    block: (reason: string | null = null): NavigationResultBlocked => ({ status: NAVIGATION_STATUS.BLOCKED, reason }),
    redirect: (target: string, options: NavigationOptions = {}): NavigationResultRedirect => ({
        status: NAVIGATION_STATUS.REDIRECT,
        target,
        options: isObject(options) ? { ...options } : {}
    })
});

const normalizeResult = (value: NavigationResultType | boolean | void | null): NavigationResultType => {
    if (!value) {
        return navigationResult.continue();
    }
    if (isBoolean(value)) {
        return value ? navigationResult.continue() : navigationResult.block();
    }
    if (!isObject(value)) {
        return navigationResult.continue();
    }
    const status = value['status'];
    if (status === NAVIGATION_STATUS.CONTINUE) {
        return navigationResult.continue(value['detail'] ?? null);
    }
    if (status === NAVIGATION_STATUS.BLOCKED) {
        const reason = isString(value['reason']) ? value['reason'] : null;
        return navigationResult.block(reason);
    }
    if (status === NAVIGATION_STATUS.REDIRECT) {
        const target = isString(value['target']) ? value['target'].trim() : '';
        if (!target) {
            return navigationResult.continue();
        }
        return navigationResult.redirect(target, value.options ?? {});
    }
    return navigationResult.continue();
};

const resolvePerformanceNow = (): (() => number) => {
    try {
        const performanceRef = getPerformance();
        if (performanceRef && isFunction(performanceRef.now)) {
            return () => performanceRef.now();
        }
    } catch (error) {
        throw ensureError(error);
    }
    return () => Date.now();
};
const emitEvent = (stage: string, data: Record<string, JsonValue | null | undefined> = {}, severity: string = 'info'): void => {
    telemetry.emit({
        module: 'NavigationMiddleware',
        stage,
        severity,
        message: stage,
        data
    });
};

const createNavigationMiddlewareController = (): NavigationMiddlewareController => {
    const stack: MiddlewareEntry[] = [];
    const boundary = new ErrorBoundary('NavigationMiddleware');
    const now = resolvePerformanceNow();
    const getTimestamp = (): number => now();
    const use = (middleware: MiddlewareHandler, options: MiddlewareOptions = {}): (() => void) => {
        if (!isFunction(middleware)) {
            throw new Error('Navigation middleware must be a function');
        }
        const rawPriority = options.priority;
        const priority = typeof rawPriority === 'number' && Number.isFinite(rawPriority) ? rawPriority : 0;
        const entry: MiddlewareEntry = {
            id: Symbol('navigation-middleware'),
            handler: middleware,
            priority,
            name: options.name || middleware.name || `middleware-${stack.length + 1}`
        };
        stack.push(entry);
        stack.sort((firstValue, secondValue) => secondValue.priority - firstValue.priority);
        return () => {
            const index = stack.indexOf(entry);
            if (index > -1) {
                stack.splice(index, 1);
            }
        };
    };
    const run = async (context: NavigationContext): Promise<NavigationResultType> => {
        const execute = async (index: number): Promise<NavigationResultType> => {
            if (index >= stack.length) {
                return navigationResult.continue();
            }
            const entry = stack[index];
            if (!entry) {
                throw new Error(`Navigation middleware entry ${index} is missing`);
            }
            const next = async (): Promise<NavigationResultType> => {
                return execute(index + 1);
            };
            const operation = async (): Promise<NavigationResultType | boolean | void | null> => {
                const startedAt = getTimestamp();
                emitEvent('middleware:start', { name: entry.name, index });
                try {
                    const result = await entry.handler(context, next);
                    const duration = getTimestamp() - startedAt;
                    emitEvent('middleware:complete', { name: entry.name, index, durationMs: Math.round(duration) });
                    return result;
                } catch (error) {
                    const duration = getTimestamp() - startedAt;
                    emitEvent(
                        'middleware:error',
                        {
                            name: entry.name,
                            index,
                            durationMs: Math.round(duration),
                            errorMessage: error instanceof Error ? coerceErrorMessage(error) : null
                        },
                        'error'
                    );
                    throw error;
                }
            };
            const value = await boundary.execute(operation, entry.name);
            return normalizeResult(value === undefined ? null : value);
        };
        return execute(0);
    };
    const clear = (): void => {
        stack.length = 0;
    };
    const size = (): number => stack.length;
    return { use, run, clear, size };
};

export { NAVIGATION_STATUS, navigationResult, createNavigationMiddlewareController };

export type { NavigationResultType, NavigationMiddlewareController, MiddlewareHandler, MiddlewareOptions };
