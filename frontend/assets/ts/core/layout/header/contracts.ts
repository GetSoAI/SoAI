/* SoAI - Shared layout header contracts [frontend/assets/ts/core/layout/header/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { StorageService } from '@core/layout/HeaderInterface.ts';

interface SidebarService {
    toggle: () => void | Promise<void>;
    isExpanded?: (() => boolean) | undefined;
    compactSidebar?: (() => void) | undefined;
}

interface SidebarCollapseApi {
    isExpanded: () => boolean;
    compactSidebar: () => void;
}

interface NotificationCenterHideHost {
    initialized?: boolean | undefined;
    hide: () => void | Promise<void>;
}

interface AuthService {
    isAuthenticated: boolean;
    logout?: (() => Promise<void>) | undefined;
}

const isSidebarService = <T>(value: T): value is T & SidebarService => {
    return isObject(value) && 'toggle' in value && isFunction(value.toggle);
};

const isSidebarCollapseApi = (value: SidebarService): value is SidebarService & SidebarCollapseApi => {
    return isFunction(value.isExpanded) && isFunction(value.compactSidebar);
};

const isNotificationCenterHideHost = <T>(value: T): value is T & NotificationCenterHideHost => {
    return isObject(value) && 'hide' in value && isFunction(value.hide);
};

const isStorageService = <T>(value: T): value is T & StorageService => {
    return isObject(value) && 'getClockFormat' in value && isFunction(value.getClockFormat) && 'setClockFormat' in value && isFunction(value.setClockFormat) && 'getHeaderClockEnabled' in value && isFunction(value.getHeaderClockEnabled) && 'getClockSecondsEnabled' in value && isFunction(value.getClockSecondsEnabled) && 'getTheme' in value && isFunction(value.getTheme) && 'setTheme' in value && isFunction(value.setTheme) && 'addRecentSearch' in value && isFunction(value.addRecentSearch);
};

const isAuthService = <T>(value: T): value is T & AuthService => {
    return isObject(value) && 'isAuthenticated' in value && typeof value.isAuthenticated === 'boolean';
};

export { isAuthService, isNotificationCenterHideHost, isSidebarCollapseApi, isSidebarService, isStorageService };
export type { AuthService, NotificationCenterHideHost, SidebarService };
