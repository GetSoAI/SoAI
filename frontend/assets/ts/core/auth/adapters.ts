/* SoAI - Shared auth adapters [frontend/assets/ts/core/auth/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireLayoutShell } from '@core/layoutShellRuntime.ts';
import { requireRouter } from '@core/routing/router/routerRuntime.ts';
import type { ApiInterface, LayoutShellInterface, RouterInterface, StateManager, StorageInterface } from '@core/auth/types.ts';

let routerModuleCache: RouterInterface | null = null;
let layoutShellModuleCache: LayoutShellInterface | null = null;

interface StateManagerCandidate {
    subscribeTabState?: (callback: StateManager['subscribeTabState']) => () => void;
    setTabState?: StateManager['setTabState'];
}

interface RouterCandidate {
    navigate?: RouterInterface['navigate'];
}

interface LayoutShellCandidate {
    teardown?: LayoutShellInterface['teardown'];
}

interface StorageCandidate {
    get?: StorageInterface['get'];
    set?: StorageInterface['set'];
    remove?: StorageInterface['remove'];
    flushPending?: StorageInterface['flushPending'];
    setAuthenticated?: StorageInterface['setAuthenticated'];
    setSession?: StorageInterface['setSession'];
    clearSession?: StorageInterface['clearSession'];
    clearRedirectAfterLogin?: StorageInterface['clearRedirectAfterLogin'];
    isWizardCompletionPending?: StorageInterface['isWizardCompletionPending'];
    setWizardCompletionPending?: StorageInterface['setWizardCompletionPending'];
}

interface ApiCandidate {
    webui?: {
        auth?: Partial<ApiInterface['webui']['auth']>;
        wizard?: Partial<ApiInterface['webui']['wizard']>;
        users?: Partial<ApiInterface['webui']['users']>;
    };
}

const isObjectValue = <T>(value: T): boolean => typeof value === 'object' && value !== null;

const isFunctionValue = <T>(value: T): boolean => typeof value === 'function';

const isStateManagerCandidate = <T>(value: T): value is T & StateManagerCandidate => isObjectValue(value);

const isRouterCandidate = <T>(value: T): value is T & RouterCandidate => isObjectValue(value);

const isLayoutShellCandidate = <T>(value: T): value is T & LayoutShellCandidate => isObjectValue(value);

const isStorageCandidate = <T>(value: T): value is T & StorageCandidate => isObjectValue(value);

const isApiCandidate = <T>(value: T): value is T & ApiCandidate => isObjectValue(value);

const hasStateInterface = <T>(candidate: T): candidate is T & StateManager => {
    if (!isStateManagerCandidate(candidate)) {
        return false;
    }
    return isFunctionValue(candidate.subscribeTabState) && isFunctionValue(candidate.setTabState);
};

const isRouterInterface = <T>(value: T): value is T & RouterInterface => {
    if (!isRouterCandidate(value)) {
        return false;
    }
    return isFunctionValue(value.navigate);
};

const isLayoutShellInterface = <T>(value: T): value is T & LayoutShellInterface => {
    if (!isLayoutShellCandidate(value)) {
        return false;
    }
    return isFunctionValue(value.teardown);
};

const isStorageInterface = <T>(value: T): value is T & StorageInterface => {
    if (!isStorageCandidate(value)) {
        return false;
    }
    return isFunctionValue(value.get) && isFunctionValue(value.set) && isFunctionValue(value.remove) && isFunctionValue(value.flushPending) && isFunctionValue(value.setAuthenticated) && isFunctionValue(value.setSession) && isFunctionValue(value.clearSession) && isFunctionValue(value.clearRedirectAfterLogin) && isFunctionValue(value.isWizardCompletionPending) && isFunctionValue(value.setWizardCompletionPending);
};

const isApiInterface = <T>(value: T): value is T & ApiInterface => {
    if (!isApiCandidate(value)) {
        return false;
    }
    const webui = value.webui;
    if (!webui || !isObjectValue(webui)) {
        return false;
    }
    const auth = webui.auth;
    const wizard = webui.wizard;
    if (!auth || !wizard || !isObjectValue(auth) || !isObjectValue(wizard)) {
        return false;
    }
    const requiredAuthMethods: (keyof ApiInterface['webui']['auth'])[] = ['getMe', 'login', 'logout', 'changePassword', 'recoverSessionRotation'];
    for (const methodName of requiredAuthMethods) {
        if (!isFunctionValue(auth[methodName])) {
            return false;
        }
    }
    const requiredWizardMethods: (keyof ApiInterface['webui']['wizard'])[] = ['status', 'complete'];
    for (const methodName of requiredWizardMethods) {
        if (!isFunctionValue(wizard[methodName])) {
            return false;
        }
    }
    const users = webui.users;
    if (!users || !isObjectValue(users) || !isFunctionValue(users.current) || !isFunctionValue(users.mutationStatus)) return false;
    return true;
};

const resolveRouter = async (): Promise<RouterInterface> => {
    if (routerModuleCache) return routerModuleCache;
    const module = requireRouter();
    if (!isRouterInterface(module)) {
        throw new Error('Router resolution failed');
    }
    routerModuleCache = module;
    return routerModuleCache;
};

const resolveLayoutShell = async (): Promise<LayoutShellInterface> => {
    if (layoutShellModuleCache) return layoutShellModuleCache;
    const module = requireLayoutShell();
    if (!isLayoutShellInterface(module)) {
        throw new Error('Layout shell resolution failed');
    }
    layoutShellModuleCache = module;
    return layoutShellModuleCache;
};

export { hasStateInterface, isApiInterface, isLayoutShellInterface, isRouterInterface, isStorageInterface, resolveLayoutShell, resolveRouter };
