/* SoAI - Settings page access state and tab gates [frontend/assets/ts/pages/settings/controllers/page/settingsAccessController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canAccessUiSurface, createAccessContextFromAuth, createSettingsTabAccessRequirement } from '@core/access/accessPolicy.ts';
import { loadWebuiPermissionsSnapshot } from '@core/access/webuiPermissions.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { resolveSoaiOsNavigationAvailability } from '@core/soaiOsAccess.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const refreshAccessState = async (page: SettingsRuntimeContext, state: SettingsPageState, signal: AbortSignal | null = null): Promise<void> => {
    const productSettingsEnabled = resolveSoaiOsNavigationAvailability();
    const permissions = await loadWebuiPermissionsSnapshot(signal ? { signal } : {});
    throwIfAborted(signal);
    state.productSettingsEnabled = productSettingsEnabled;
    state.grantedActions = permissions.grantedActions;
    state.advancedAccessEnabled = page.owners.auth.isAdmin() && state.grantedActions.has('CONFIG_PATCH');
    if (!state.advancedAccessEnabled) {
        state.advancedMode = false;
    }
};

const isNormalTabVisible = (page: SettingsRuntimeContext, state: SettingsPageState, definition: { adminOnly?: boolean; osOnly?: boolean; actions?: readonly string[] }): boolean => {
    return canAccessUiSurface(createSettingsTabAccessRequirement(definition), createAccessContextFromAuth(page.owners.auth, { soaiOsAvailable: state.productSettingsEnabled, grantedActions: state.grantedActions }));
};

const isSettingsNormalTabVisibleById = (page: SettingsRuntimeContext, state: SettingsPageState, tabId: string): boolean => {
    const definition = page.edition.normalTabs.find((candidate) => candidate.id === tabId);
    if (!definition) {
        throw new Error(`Settings tab "${tabId}" is not defined`);
    }
    return isNormalTabVisible(page, state, definition);
};

const hasSettingsAction = (state: SettingsPageState, action: string): boolean => state.grantedActions.has(action);

const canManageInstanceIdentity = (page: SettingsRuntimeContext, state: SettingsPageState): boolean => page.owners.auth.isAdmin() && hasSettingsAction(state, 'CONFIG_PATCH');

export { canManageInstanceIdentity, hasSettingsAction, isNormalTabVisible, isSettingsNormalTabVisibleById, refreshAccessState };
