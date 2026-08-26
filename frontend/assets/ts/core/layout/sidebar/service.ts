/* SoAI - Shared layout sidebar service [frontend/assets/ts/core/layout/sidebar/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canAccessUiSurface, createAccessContextFromUser, createAccessRequirement } from '@core/access/accessPolicy.ts';
import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { MAIN_STATE_SERVICE_ID } from '@core/indicators/protocols.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { isSidebarStorageConfigContract, type ComponentRegistryContract, type SidebarStorageConfigContract, type UserInfo } from '@core/layout/sidebar/contracts.ts';
import { SIDEBAR_BASE_WIDTH_PROPERTY, SIDEBAR_EXPANDED_WIDTH_PROPERTY, SIDEBAR_LABEL_SELECTOR, SIDEBAR_LINK_SELECTOR } from '@core/layout/sidebar/dom.ts';
import { normalizeComponentToken } from '@core/layout/sidebar/foundation.ts';
import { isSidebarStoragePluginIndicatorContract, type SidebarStoragePluginIndicatorContract } from '@core/layout/sidebar/pluginIndicator.ts';
import type { SidebarState } from '@core/layout/sidebar/state.ts';
import type { ComponentInstance } from '@core/componentsupport/types.ts';
import type { SidebarComponentInstance, SidebarConfigEntry } from '@core/layout/sidebar/view.ts';
import { resolveKernelService, resolveOptionalKernelService } from '@core/runtime/runtimeContext.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { isFunction, isObject, isStringArray } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync, requireIconName } from '@core/ui/icons/iconservice/public.ts';

const isSidebarComponentInstance = (value: SoAIRegisteredService | ComponentInstance | null): value is ComponentInstance & SidebarComponentInstance => {
    if (!isObject(value)) {
        return false;
    }
    const initializeValid = !('initialize' in value) || value.initialize === undefined || isFunction(value.initialize);
    const collapseValid = !('setCollapsed' in value) || value.setCollapsed === undefined || isFunction(value.setCollapsed);
    return initializeValid && collapseValid;
};

const requireSidebarStorageConfig = (): SidebarStorageConfigContract => {
    const storage = resolveKernelService('core.storage');
    if (!isSidebarStorageConfigContract(storage)) {
        throw new Error('Storage service must expose sidebar configuration accessors');
    }
    return storage;
};

const getVisibleSidebarConfig = (sidebarConfig: SidebarConfigEntry[], adminOnlyItems: Set<string>, user: UserInfo | null, grantedActions: ReadonlySet<string>): SidebarConfigEntry[] => {
    const storage = requireSidebarStorageConfig();
    const hiddenPages = storage.getHiddenSidebarPages();
    if (!isStringArray(hiddenPages)) {
        throw new TypeError('Storage service getHiddenSidebarPages must return a string array');
    }
    const showIndicator = storage.getShowMainStatusIndicator();
    if (typeof showIndicator !== 'boolean') {
        throw new TypeError('Storage service getShowMainStatusIndicator must return a boolean');
    }

    const hidden: string[] = hiddenPages;
    return sidebarConfig.filter((entry) => {
        if (!entry.id) {
            return true;
        }
        const requirement = createAccessRequirement({
            authenticated: true,
            admin: adminOnlyItems.has(entry.id),
            actions: entry.actions
        });
        const accessContext = createAccessContextFromUser(user, {
            terminalAllowed: entry.id === 'terminal' ? user?.isAdmin === true || grantedActions.has('TERMINAL_USE') : true,
            grantedActions
        });
        if (!canAccessUiSurface(requirement, accessContext)) {
            return false;
        }
        if (entry.id === 'main-state' && !showIndicator) {
            return false;
        }
        return !hidden.includes(entry.id);
    });
};

const resolveSidebarLabel = (cfg: SidebarConfigEntry): string => {
    if (cfg.getLabel && isFunction(cfg.getLabel)) {
        return cfg.getLabel();
    }
    if (cfg.type === 'page') {
        throw new Error(`Sidebar page entry ${cfg.id ?? '<unknown>'} is missing getLabel`);
    }
    if (cfg.label) {
        return cfg.label;
    }
    return cfg.id || '';
};

const resolveSidebarIconMarkup = (icon: IconName | null | undefined): TrustedHtml => {
    if (!icon) {
        throw new Error('Sidebar page entry requires an icon');
    }
    const resolved = requireIconName(icon, 'Sidebar icon');
    return getIconSync(resolved);
};

const resolveSidebarStorage = (storage: SidebarStoragePluginIndicatorContract | null): SidebarStoragePluginIndicatorContract | null => {
    if (storage) {
        return storage;
    }
    try {
        const nextStorage = resolveKernelService('core.storage');
        if (!isSidebarStoragePluginIndicatorContract(nextStorage)) {
            errorHandler.warn('Sidebar', 'Storage service is not ready for sidebar operations');
            return null;
        }
        return nextStorage;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.debug('Sidebar', 'Storage resolution failed', runtimeError);
        throw ensureError(error);
    }
};

const getSidebarComponentByPath = (componentRegistry: ComponentRegistryContract | null, name: string | null): SidebarComponentInstance | null => {
    const token = normalizeComponentToken(name);
    if (!token) {
        return null;
    }

    if (componentRegistry) {
        const fromRegistry = componentRegistry.get(token) ?? null;
        if (isSidebarComponentInstance(fromRegistry)) {
            return fromRegistry;
        }
    }

    const fromContainer = resolveOptionalKernelService(token);
    if (isSidebarComponentInstance(fromContainer)) {
        return fromContainer;
    }

    return null;
};

const waitForSidebarComponent = async (componentRegistry: ComponentRegistryContract | null, name: string | null, _timeoutMs: number): Promise<SidebarComponentInstance> => {
    const token = normalizeComponentToken(name);
    if (!token) {
        throw new Error('Sidebar component identifier is required');
    }

    const component = getSidebarComponentByPath(componentRegistry, token);
    if (!component) {
        throw new Error(`Sidebar component "${token}" is not registered`);
    }
    return component;
};

const resolveSidebarCssPixelValue = (sidebar: HTMLElement, propertyName: string): number => {
    const propertyValue = window.getComputedStyle(sidebar).getPropertyValue(propertyName).trim();
    const resolvedValue = Number.parseFloat(propertyValue);
    return Number.isFinite(resolvedValue) ? resolvedValue : 0;
};

const resolveSidebarExpandedWidth = (sidebar: HTMLElement): number => {
    const minimumWidth = resolveSidebarCssPixelValue(sidebar, SIDEBAR_BASE_WIDTH_PROPERTY);
    const maxViewportWidth = Math.max(minimumWidth, measureLayoutViewport(sidebar).width - 24);
    let requiredWidth = minimumWidth;
    const iconRailWidth = resolveSidebarCssPixelValue(sidebar, '--sidebar-icon-rail');
    const borderInlineStart = resolveSidebarCssPixelValue(sidebar, '--sidebar-border-inline-start-width');
    const borderInlineEnd = resolveSidebarCssPixelValue(sidebar, '--sidebar-border-inline-end-width');
    const borderInlineTotal = Math.max(borderInlineStart + borderInlineEnd, 0);
    const labels = dom.resolveAll(SIDEBAR_LABEL_SELECTOR, sidebar);
    for (const labelNode of labels) {
        if (!(labelNode instanceof HTMLElement)) {
            continue;
        }
        const linkNode = labelNode.closest(SIDEBAR_LINK_SELECTOR);
        if (!(linkNode instanceof HTMLElement) || linkNode.offsetParent === null) {
            continue;
        }
        const linkStyles = window.getComputedStyle(linkNode);
        const columnGap = Number.parseFloat(linkStyles.columnGap || '0');
        const resolvedColumnGap = Number.isFinite(columnGap) ? columnGap : 0;

        const labelFullWidth = labelNode.scrollWidth;
        const candidateWidth = borderInlineTotal + iconRailWidth + resolvedColumnGap + labelFullWidth;
        if (candidateWidth > requiredWidth) {
            requiredWidth = candidateWidth;
        }
    }
    return Math.ceil(Math.min(requiredWidth, maxViewportWidth));
};

const syncSidebarExpandedWidth = (sidebar: HTMLElement | null): void => {
    if (!sidebar) {
        return;
    }
    const expandedWidth = resolveSidebarExpandedWidth(sidebar);
    sidebar.style.setProperty(SIDEBAR_EXPANDED_WIDTH_PROPERTY, `${expandedWidth}px`);
};

const updateSidebarMainStateIndicator = (componentRegistry: ComponentRegistryContract | null, state: SidebarState): void => {
    const component = getSidebarComponentByPath(componentRegistry, MAIN_STATE_SERVICE_ID);
    if (component) {
        component.setCollapsed?.(state.mobile ? !state.open : state.collapsed);
    }
};

const loadSidebarGrantedActions = async (user: UserInfo | null): Promise<ReadonlySet<string>> => {
    if (!user) {
        return new Set();
    }
    try {
        return (await loadWebuiPermissionsSnapshot()).grantedActions;
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('Sidebar', 'Failed to load webui.permissions snapshot', runtimeError);
        return new Set();
    }
};

const captureSidebarAuthSnapshot = (user: UserInfo | null | undefined): UserInfo | null => user || null;

export { captureSidebarAuthSnapshot, getSidebarComponentByPath, getVisibleSidebarConfig, loadSidebarGrantedActions, resolveSidebarIconMarkup, resolveSidebarLabel, resolveSidebarStorage, syncSidebarExpandedWidth, updateSidebarMainStateIndicator, waitForSidebarComponent };
