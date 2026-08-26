/* SoAI - Shared routing navigation middleware normalization [frontend/assets/ts/core/routing/router/navigationMiddlewareNormalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { NAVIGATION_STATUS, navigationResult, type NavigationResultType } from '@core/navigationMiddleware.ts';
import type { NavigationOptions } from '@core/routing/router/types.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { isJsonValue } from '@core/types/jsonValues.ts';

interface ErrorMessageCarrier {
    readonly message?: string | undefined;
}

const isNavigationOptions = <T>(value: T): value is T & NavigationOptions => isObject(value);

export const normalizeMiddlewareOutcome = (value: NavigationResultType | boolean | void | null): NavigationResultType => {
    if (value === false) {
        return navigationResult.block();
    }
    if (value === true) {
        return navigationResult.continue();
    }
    if (value === null || value === undefined) {
        return navigationResult.continue();
    }
    if (!isObject(value) || !isString(value['status'])) {
        return navigationResult.continue();
    }
    const status = value['status'];
    if (status === NAVIGATION_STATUS.REDIRECT) {
        const target = value['target'];
        if (!isString(target) || !target) {
            throw new Error('Navigation middleware redirect must include target');
        }
        const optionsValue = value['options'];
        return navigationResult.redirect(target, isNavigationOptions(optionsValue) ? optionsValue : {});
    }
    if (status === NAVIGATION_STATUS.BLOCKED) {
        const reasonValue = value['reason'];
        const reason = isString(reasonValue) ? reasonValue : null;
        return navigationResult.block(reason);
    }
    if (status === NAVIGATION_STATUS.CONTINUE) {
        const detail = isObject(value) ? (value['detail'] ?? null) : null;
        return navigationResult.continue(isJsonValue(detail) ? detail : null);
    }
    throw new Error(`Unknown middleware status: ${status}`);
};

export const readErrorMessage = <T>(error: T | Error | null | undefined): string | null => {
    if (error instanceof Error) return error.message || null;
    if (isObject(error)) {
        const candidate: ErrorMessageCarrier = error;
        const message = candidate.message ?? null;
        if (isString(message) && message) return message;
    }
    return null;
};
