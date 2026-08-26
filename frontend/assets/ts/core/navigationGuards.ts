/* SoAI - Shared frontend navigation guards [frontend/assets/ts/core/navigationGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { navigationResult, type NavigationResultType } from '@core/navigationMiddleware.ts';
import { isFunction, isObject, isString, isSymbol } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';

type GuardFunction = (context: NavigationContext) => Promise<boolean | undefined | NavigationResultType> | boolean | undefined | NavigationResultType;

interface GuardOptions {
    id?: string | symbol | undefined;
}

interface GuardRegistry {
    register: (guard: GuardFunction, options?: GuardOptions) => () => void;
    list: () => GuardFunction[];
}

interface UnsavedChangesGuardOptions {
    hasUnsavedChanges: () => boolean;
    shouldPromptOnNavigation?: (context: NavigationContext) => Promise<boolean> | boolean;
    getMessage?: (() => string) | string;
    confirmNavigation?: (context: NavigationContext) => Promise<boolean> | boolean;
    id?: string | symbol;
    scope?: Window | null;
    addEventListener?: EventBinderFunctionValue;
}

type EventBinderFunctionValue = (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => () => void;

const isNavigationResultType = (value: NavigationResultType | boolean | null | undefined): value is NavigationResultType => {
    if (!isObject(value)) return false;
    const status = value['status'];
    if (status !== 'continue' && status !== 'blocked' && status !== 'redirect') {
        return false;
    }
    if (status === 'redirect') {
        return isString(value['target']) && value['target'].trim().length > 0;
    }
    return true;
};

const createGuardRegistry = (): GuardRegistry => {
    const entries = new Map<string | symbol, GuardFunction>();
    const register = (guard: GuardFunction, options: GuardOptions = {}): (() => void) => {
        if (!isFunction(guard)) {
            throw new Error('Navigation guard must be a function');
        }
        const key = isString(options.id) && options.id ? options.id : isSymbol(options.id) ? options.id : Symbol('navigation-guard');
        entries.set(key, guard);
        return () => {
            entries.delete(key);
        };
    };
    const list = (): GuardFunction[] => Array.from(entries.values());
    return { register, list };
};

const dirtyStateRegistry = createGuardRegistry();

const registerDirtyStateGuard = (guard: GuardFunction, options: GuardOptions = {}): (() => void) => dirtyStateRegistry.register(guard, options);

const evaluateDirtyStateGuards = async (context: NavigationContext): Promise<NavigationResultType | null> => {
    const guards = dirtyStateRegistry.list();
    for (const guard of guards) {
        const verdict = await guard(context);
        if (verdict === undefined) {
            continue;
        }
        if (verdict === false) {
            return navigationResult.block('dirty-state');
        }
        if (isNavigationResultType(verdict)) {
            return verdict;
        }
    }
    return null;
};

const normalizeMessageResolver = (message: (() => string) | string | undefined): (() => string) => {
    if (isFunction(message)) {
        return () => {
            const value = message();
            return typeof value === 'string' ? value.trim() : '';
        };
    }
    const normalized = isString(message) ? message.trim() : '';
    return () => normalized;
};

const defaultEventBinder: EventBinderFunctionValue = (target, event, handler, options) => {
    target.addEventListener(event, handler, options);
    return () => target.removeEventListener(event, handler, options);
};

interface BeforeUnloadOptions {
    hasUnsavedChanges: () => boolean;
    getMessage: () => string;
    scope?: Window | null | undefined;
    addEventListener?: EventBinderFunctionValue | undefined;
}

const registerBeforeUnloadPrompt = ({ hasUnsavedChanges, getMessage, scope, addEventListener }: BeforeUnloadOptions): (() => void) => {
    const target = scope || getWindow();
    if (!target || !isFunction(target.addEventListener)) return () => {};
    const binder = isFunction(addEventListener) ? addEventListener : defaultEventBinder;
    const handler = (event: BeforeUnloadEvent): string | void => {
        if (!hasUnsavedChanges()) return;
        const message = getMessage();
        if (!message) return;
        event.preventDefault();
        event.returnValue = message;
        return message;
    };
    const cleanup = binder(target, 'beforeunload', handler) || (() => {});
    return () => {
        try {
            cleanup();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('navigationGuards', 'Cleanup failed for beforeunload handler', runtimeError);
        }
    };
};

const registerUnsavedChangesGuard = ({ hasUnsavedChanges, shouldPromptOnNavigation, getMessage, confirmNavigation, id, scope, addEventListener }: UnsavedChangesGuardOptions): (() => void) => {
    if (!isFunction(hasUnsavedChanges)) {
        throw new Error('registerUnsavedChangesGuard requires a hasUnsavedChanges function');
    }
    const resolveMessage = normalizeMessageResolver(getMessage);
    const navigationCheck = isFunction(shouldPromptOnNavigation) ? shouldPromptOnNavigation : () => hasUnsavedChanges();
    const confirm = isFunction(confirmNavigation) ? confirmNavigation : null;
    const beforeUnloadCleanup = registerBeforeUnloadPrompt({
        hasUnsavedChanges,
        getMessage: resolveMessage,
        scope,
        addEventListener
    });
    const guardCleanup = registerDirtyStateGuard(
        async (context: NavigationContext) => {
            const needsPrompt = !!(await navigationCheck(context));
            if (!needsPrompt) return true;
            const verdict = confirm ? await confirm(context) : false;
            return verdict ?? false;
        },
        { id }
    );
    return () => {
        beforeUnloadCleanup?.();
        guardCleanup?.();
    };
};

export { registerDirtyStateGuard, evaluateDirtyStateGuards, registerUnsavedChangesGuard };

export type { GuardFunction, GuardOptions, UnsavedChangesGuardOptions, NavigationResultType };
