/* SoAI - Settings page control layer adapters [frontend/assets/ts/pages/settings/controllers/page/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { McpConnection, McpDataBundle, McpInteractionEntry, McpPromptEntry, McpResourceEntry, McpRootEntry, McpSearchKeyEntry, McpServer, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { McpManager, MessagingManager } from '@features/settings/public.ts';
import { canManageInstanceIdentity, hasSettingsAction } from '@pages/settings/controllers/page/settingsAccessController.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { createExternalAccountsManager } from '@pages/settings/controllers/page/externalAccountsManager.ts';
import { createPreferencesManagerHost, createSystemManagerHost, createThemeManagerHost, createUsersManagerHost } from '@pages/settings/controllers/page/managerhosts/adapters.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import { buildBaseHostBindings, hasSearchQuery } from '@pages/settings/controllers/page/hostBindings.ts';
import { PreferencesManager } from '@pages/settings/controllers/PreferencesManager.ts';
import { SystemManager } from '@pages/settings/controllers/systemmanager/SystemManager.ts';
import { ThemeManager } from '@pages/settings/controllers/thememanager/ThemeManager.ts';
import { UsersManager } from '@pages/settings/controllers/UsersManager.ts';
import { resolveWorkspaceBrowserAccess } from '@core/fileexplorerbrowser/workspaceBrowserAccess.ts';
import { InstanceIdentityManager } from '@pages/settings/controllers/instanceidentity/InstanceIdentityManager.ts';

const createCoreSettingsManagers = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): void => {
    if (canManageInstanceIdentity(page, state)) {
        if (!state.instanceIdentity) {
            throw new Error('Instance identity is required for administrators');
        }
        state.instanceIdentityManager = new InstanceIdentityManager({
            host: {
                pageDom: page.owners.pageDom,
                pageResources: page.owners.pageResources,
                updateInstanceName: async (instanceName: string | null): Promise<string | null> => (await page.owners.api.system.updateInstanceName(instanceName)).instanceName,
                notifySaveChanged: callbacks.notifySaveChanged,
                syncManualDirtyField: callbacks.syncManualDirtyField,
                clearManualDirtyField: callbacks.clearManualDirtyField
            },
            instanceId: state.instanceIdentity.instanceId,
            instanceName: state.instanceIdentity.instanceName
        });
    }
    state.preferencesManager = new PreferencesManager({
        host: createPreferencesManagerHost(page, state, callbacks)
    });
    state.themeManager = new ThemeManager({
        host: createThemeManagerHost(page, state, callbacks),
        canManageSolidBackground: page.owners.auth.isAdmin(),
        getGrantedActions: (): ReadonlySet<string> => state.grantedActions,
        dashboardProductTitle: () => page.edition.dashboardTitle,
        updatePreferenceToggleLabel: callbacks.updatePreferenceToggleLabel
    });
    const baseBindings = buildBaseHostBindings(page, callbacks);
    state.messagingManager = new MessagingManager({
        host: {
            ...baseBindings,
            api: page.owners.api.webui.messaging.accounts,
            resolveWorkspaceBrowserAccess: async () =>
                await resolveWorkspaceBrowserAccess({
                    getCurrentUser: () => page.owners.api.webui.auth.getMe(),
                    scopedBrowserApi: page.owners.api.fileExplorer
                }),
            hasSearchQuery: (): boolean => hasSearchQuery(page)
        }
    });

    if (page.owners.auth.isAdmin()) {
        state.mcpManager = new McpManager({
            host: {
                services: {
                    api: page.owners.api,
                    isAdmin: (): boolean => page.owners.auth.isAdmin(),
                    getCurrentUserId: (): number => {
                        const currentUser = page.owners.auth.getCurrentUser();
                        const rawId = currentUser?.id;
                        const normalized = typeof rawId === 'number' ? rawId : typeof rawId === 'string' ? Number(rawId) : NaN;
                        if (!Number.isInteger(normalized) || normalized <= 0) {
                            throw new Error('MCP token provisioning requires an authenticated user id');
                        }
                        return normalized;
                    },
                    hasSearchQuery: (): boolean => hasSearchQuery(page),
                    createDebouncedHandler: (handler, debounceTime) => page.owners.services.createDebouncedHandler(handler, debounceTime),
                    pageContext: page.owners.pageContext,
                    dom: page.owners.dom,
                    filterSettings: callbacks.filterSettings
                },
                view: {
                    pageDom: page.owners.pageDom,
                    pageResources: page.owners.pageResources,
                    updatePreferenceToggleLabel: callbacks.updatePreferenceToggleLabel,
                    updateProperty: (element: Element, property: string, value: DomPropertyValue): void => page.owners.pageDom.updateProperty(element, property, value),
                    warnAndFocus: callbacks.warnAndFocus
                },
                execution: {
                    feedback: page.owners.feedback,
                    runWithBoundary: (name, task) => page.owners.pageLifecycle.run(name, task),
                    withButtonDisabled: callbacks.withButtonDisabled,
                    confirmAndExecute: callbacks.confirmAndExecute,
                    notifySaveChanged: callbacks.notifySaveChanged,
                    requestSave: callbacks.requestSave,
                    syncManualDirtyField: callbacks.syncManualDirtyField,
                    clearManualDirtyField: callbacks.clearManualDirtyField
                },
                data: {
                    canPatchCoreConfig: (): boolean => hasSettingsAction(state, 'CONFIG_PATCH'),
                    getCoreConfig: (): JsonObject => state.coreConfig,
                    getMcpData: (): McpDataBundle => ({
                        status: state.mcpStatus,
                        servers: state.mcpServers,
                        connections: state.mcpConnections,
                        searchKeys: state.mcpSearchKeys,
                        searchProviders: state.mcpSearchProviders,
                        roots: state.mcpRoots,
                        interactions: state.mcpInteractions,
                        tools: state.mcpTools,
                        resources: state.mcpResources,
                        prompts: state.mcpPrompts
                    }),
                    setMcpStatus: (statusValue: McpStatus | null): void => {
                        state.mcpStatus = statusValue;
                    },
                    setMcpServers: (serversValue: McpServer[]): void => {
                        state.mcpServers = serversValue;
                    },
                    setMcpConnections: (connectionsValue: McpConnection[]): void => {
                        state.mcpConnections = connectionsValue;
                    },
                    setMcpSearchKeys: (keysValue: McpSearchKeyEntry[]): void => {
                        state.mcpSearchKeys = keysValue;
                    },
                    setMcpSearchProviders: (providersValue: string[]): void => {
                        state.mcpSearchProviders = providersValue;
                    },
                    setMcpRoots: (rootsValue: McpRootEntry[]): void => {
                        state.mcpRoots = rootsValue;
                    },
                    setMcpInteractions: (interactionsValue: McpInteractionEntry[]): void => {
                        state.mcpInteractions = interactionsValue;
                    },
                    setMcpTools: (toolsValue: McpToolEntry[]): void => {
                        state.mcpTools = toolsValue;
                    },
                    setMcpResources: (resourcesValue: McpResourceEntry[]): void => {
                        state.mcpResources = resourcesValue;
                    },
                    setMcpPrompts: (promptsValue: McpPromptEntry[]): void => {
                        state.mcpPrompts = promptsValue;
                    }
                },
                editing: {
                    getMcpServerEditId: (): string | null => state.mcpServerEditId,
                    setMcpServerEditId: (id: string | null): void => {
                        state.mcpServerEditId = id;
                    },
                    getMcpServerEditBaseline: (): McpServer | null => state.mcpServerEditBaseline,
                    setMcpServerEditBaseline: (server: McpServer | null): void => {
                        state.mcpServerEditBaseline = server;
                    },
                    getMcpRootEditIndex: (): number | null => state.mcpRootEditIndex,
                    setMcpRootEditIndex: (index: number | null): void => {
                        state.mcpRootEditIndex = index;
                    },
                    rebindConfigForm: callbacks.rebindConfigForm
                }
            }
        });
    }
    createExternalAccountsManager(page, state, callbacks);

    const settingsContribution = page.edition.product;
    const hostApi = page.owners.api.os;
    if (state.productSettingsEnabled && (settingsContribution === null || hostApi === null)) {
        throw new Error('Trusted host user settings are unavailable for the selected frontend edition');
    }
    state.usersManager = new UsersManager({
        host: createUsersManagerHost(page, state, callbacks),
        productContribution: state.productSettingsEnabled && settingsContribution !== null && hostApi !== null ? settingsContribution.createUsers(hostApi.users) : null
    });
    if (page.owners.auth.isAdmin()) {
        state.systemManager = new SystemManager({
            host: createSystemManagerHost(page, state, callbacks)
        });
    }
};

export { createCoreSettingsManagers };
