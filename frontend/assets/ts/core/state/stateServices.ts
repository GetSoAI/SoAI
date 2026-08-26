/* SoAI - Frontend state service ownership [frontend/assets/ts/core/state/stateServices.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { dom } from '@core/dom/dom.ts';
import { getApiClient } from '@core/api/service.ts';
import { getAuthManager } from '@core/auth/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { STATUS } from '@core/realtime/streammanager/resources/ids.ts';
import { requireStreamManager } from '@core/realtime/streammanager/runtime.ts';
import { SectionTracker } from '@core/state/SectionTracker.ts';
import { StateManager } from '@core/state/StateManager.ts';
import { StatusManager } from '@core/state/statusmanager/service.ts';
import type { ApiClient, AuthService } from '@core/state/statusmanager/contracts.ts';
import type { DomService } from '@core/state/types.ts';
import { UIStateManager } from '@core/state/UIStateManager.ts';
import { hasFunctionProperty, hasOwn, isHTMLElement, isObject, isString } from '@core/typeGuards.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';

const isDomService = <T>(value: T): value is T & DomService => {
    if (!isObject(value)) {
        return false;
    }
    const requiredMethods: readonly string[] = ['resolve', 'resolveAll', 'getDocument', 'getDocumentElement', 'toggleClass', 'addClass', 'removeClass', 'setText', 'setHTML', 'setStyle', 'getData'];
    return requiredMethods.every((method) => hasFunctionProperty(value, method));
};

const isApiClient = <T>(value: T): value is T & ApiClient => {
    if (!isObject(value)) {
        return false;
    }
    if (!('system' in value)) return true;
    const system = value.system;
    if (system === undefined) {
        return true;
    }
    if (!isObject(system)) {
        return false;
    }
    return !hasOwn(system, 'stateDefinitions') || hasFunctionProperty(system, 'stateDefinitions');
};

const isAuthService = <T>(value: T): value is T & AuthService => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'onLogin') && hasFunctionProperty(value, 'onLogout') && 'isAuthenticated' in value && typeof value.isAuthenticated === 'boolean';
};

const createStateManager = (): StateManager => {
    if (!isDomService(dom)) {
        throw new Error('DOM service is unavailable for state manager');
    }
    return new StateManager({
        dom,
        errorHandler,
        resolveElement: (target: string | Element | null | undefined): HTMLElement | null => {
            if (isHTMLElement(target)) {
                return target;
            }
            if (isString(target)) {
                const resolved = dom.resolve(target);
                return isHTMLElement(resolved) ? resolved : null;
            }
            return null;
        },
        defaultHiddenClass: CSS_CLASSES.HIDDEN,
        statusStreamId: STATUS,
        apiClientProvider: async (): Promise<ApiClient | null> => {
            const api = getApiClient();
            if (!isApiClient(api)) {
                throw new Error('core.apiClient must satisfy the API client interface');
            }
            return api;
        },
        authServiceProvider: async (): Promise<AuthService> => {
            const auth = getAuthManager();
            if (!isAuthService(auth)) {
                throw new Error('core.auth must satisfy the auth service interface');
            }
            return auth;
        },
        streamManagerProvider: () => requireStreamManager()
    });
};

const getStateManager = (): StateManager => {
    const candidate = resolveKernelService('core.state');
    if (!(candidate instanceof StateManager)) {
        throw new Error('core.state is not registered');
    }
    return candidate;
};

const resetStateManager = (): void => {
    getStateManager().destroy();
};

const getStatusManager = (): StateManager['status'] => getStateManager().status;
const getSectionTracker = (): StateManager['section'] => getStateManager().section;
const getUIState = (): StateManager['ui'] => getStateManager().ui;

const StateManagement = Object.freeze({
    StateManager,
    UIStateManager,
    StatusManager,
    SectionTracker
});

export { StateManager, UIStateManager, StatusManager, SectionTracker, createStateManager, getStateManager, getStatusManager, getSectionTracker, getUIState, resetStateManager, StateManagement };
