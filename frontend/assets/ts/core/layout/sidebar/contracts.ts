/* SoAI - Shared layout sidebar contracts [frontend/assets/ts/core/layout/sidebar/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AuthManager } from '@core/auth/service.ts';
import { ComponentRegistry } from '@core/componentsupport/registry.ts';
import type { ComponentInstance } from '@core/componentsupport/types.ts';
import type { WebuiUser } from '@core/auth/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
type UserInfo = Pick<WebuiUser, 'isAdmin'>;
type AuthManagerContract = Pick<AuthManager, 'user' | 'onLogin' | 'onLogout'>;

interface ComponentRegistryContract {
    get: (name: string) => ComponentInstance | undefined;
    register: (name: string, instance: ComponentInstance | null | undefined, options?: Record<string, JsonValue | null | undefined>) => ComponentInstance;
}

interface SidebarStorageConfigContract {
    getHiddenSidebarPages: () => JsonValue | null | undefined;
    getShowMainStatusIndicator: () => JsonValue | null | undefined;
}

const resolveComponentRegistry = (value: ComponentRegistry | null | undefined): ComponentRegistryContract | null => (value instanceof ComponentRegistry ? value : null);

const resolveAuthManager = (value: AuthManager | null | undefined): AuthManagerContract | null => {
    return value instanceof AuthManager ? value : null;
};

const isSidebarStorageConfigContract = (value: SidebarStorageConfigContract | null | undefined): value is SidebarStorageConfigContract => {
    if (!isObject(value)) return false;
    return 'getHiddenSidebarPages' in value && isFunction(value.getHiddenSidebarPages) && 'getShowMainStatusIndicator' in value && isFunction(value.getShowMainStatusIndicator);
};

export { isSidebarStorageConfigContract, resolveAuthManager, resolveComponentRegistry };
export type { AuthManagerContract, ComponentRegistryContract, SidebarStorageConfigContract, UserInfo };
