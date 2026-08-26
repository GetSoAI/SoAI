/* SoAI - Settings feature MCP container handlers controller [frontend/assets/ts/features/settings/mcp/mcpContainerHandlersController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { i18n } from '@core/i18n/index.ts';
import { narrowSelect } from '@core/dom/narrowElement.ts';
import { requireButtonElement, requireSelectElement } from '@core/dom/typedElements.ts';
import { applyMcpToolGroupToggle } from '@core/mcp/toolGroupToggle.ts';
import { UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import { isMcpChangeActionId, isMcpClickActionId, MCP_ACTION_ACCESS_TOKEN_CREATE, MCP_ACTION_ACCESS_TOKEN_REVOKE, MCP_ACTION_INTERACTION_ACTION_CHANGE, MCP_ACTION_INTERACTION_RESOLVE, MCP_ACTION_REFRESH, MCP_ACTION_ROOT_CANCEL, MCP_ACTION_ROOT_DELETE, MCP_ACTION_ROOT_EDIT, MCP_ACTION_SEARCH_DELETE, MCP_ACTION_SEARCH_EDIT, MCP_ACTION_SEARCH_PROVIDER_CHANGE, MCP_ACTION_SECTION_TOGGLE, MCP_ACTION_SERVER_ADD, MCP_ACTION_SERVER_AUTHORIZE, MCP_ACTION_SERVER_CLEAR_AUTH, MCP_ACTION_SERVER_CONNECT, MCP_ACTION_SERVER_DELETE, MCP_ACTION_SERVER_DISCONNECT, MCP_ACTION_SERVER_EDIT, MCP_ACTION_SERVER_ENABLED_CHANGE, type McpChangeActionId, type McpClickActionId } from '@features/settings/mcp/actions.ts';
import type { McpConnectionsManager } from '@features/settings/mcp/mcpConnections.ts';
import type { McpInteractionsManager } from '@features/settings/mcp/mcpInteractions.ts';
import type { McpAccessTokensManager } from '@features/settings/mcp/mcpAccessTokens.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { McpRootsManager } from '@features/settings/mcp/mcpRoots.ts';
import type { McpSearchKeysManager } from '@features/settings/mcp/mcpSearchKeys.ts';
import type { McpServersManager } from '@features/settings/mcp/mcpServers.ts';

type McpContainerHandlersHost = Pick<McpManagerHost, 'execution' | 'view'>;

type McpContainerHandlersDependencies = {
    host: McpContainerHandlersHost;
    container: HTMLElement;
    isAdmin: boolean;
    reload: () => Promise<boolean>;
    accessTokens: McpAccessTokensManager;
    servers: McpServersManager;
    connections: McpConnectionsManager;
    searchKeys: McpSearchKeysManager;
    roots: McpRootsManager;
    interactions: McpInteractionsManager;
    persistSectionExpansion: (sectionId: string, expanded: boolean) => void;
    requireDataValue: (element: Element, key: string) => string;
    requireNonNegativeIndex: (element: Element, key: string) => number;
};

const bindMcpContainerHandlers = (dependencies: McpContainerHandlersDependencies): Array<() => void> => {
    const { host, container } = dependencies;
    const cleanups: Array<() => void> = [];

    requireButtonElement(host.view.pageDom, UI_IDS.MCP_ACCESS_TOKEN_CREATE, 'MCP control', container);

    if (dependencies.isAdmin) {
        requireButtonElement(host.view.pageDom, UI_IDS.MCP_REFRESH, 'MCP control', container);
        requireButtonElement(host.view.pageDom, UI_IDS.MCP_SERVER_ADD, 'MCP control', container);
        requireButtonElement(host.view.pageDom, UI_IDS.MCP_ROOT_CANCEL, 'MCP control', container);

        const searchProviderSelect = requireSelectElement(host.view.pageDom, UI_IDS.MCP_SEARCH_PROVIDER_SELECT, 'MCP control', container);
        dependencies.searchKeys.syncSearchProviderFields(searchProviderSelect);
    }

    const clickHandlers: Partial<Record<McpClickActionId, (actionElement: HTMLElement, eventObject: Event) => Promise<void>>> = {
        [MCP_ACTION_SECTION_TOGGLE]: async (actionElement: HTMLElement, eventObject: Event) => {
            if (actionElement.classList.contains('section-header') && eventObject.target instanceof Element && eventObject.target.closest('.section-header-end')) {
                return;
            }
            const result = applyMcpToolGroupToggle(actionElement);
            dependencies.persistSectionExpansion(result.serverId, result.expanded);
        },
        [MCP_ACTION_ACCESS_TOKEN_CREATE]: async () => {
            await dependencies.accessTokens.openCreateFlow();
        },
        [MCP_ACTION_ACCESS_TOKEN_REVOKE]: async (actionElement: HTMLElement) => {
            await dependencies.accessTokens.revokeToken(dependencies.requireDataValue(actionElement, 'token_id'), dependencies.reload);
        }
    };

    if (dependencies.isAdmin) {
        clickHandlers[MCP_ACTION_REFRESH] = async (): Promise<void> => {
            if (await dependencies.reload()) {
                dependencies.host.execution.feedback.show(i18n.t('common.notifications.refreshCompleted'), 'refresh');
            }
        };
        clickHandlers[MCP_ACTION_SERVER_ADD] = async () => dependencies.servers.openCreateModal();
        clickHandlers[MCP_ACTION_SERVER_EDIT] = async (actionElement: HTMLElement) => dependencies.servers.openEditModal(dependencies.requireDataValue(actionElement, 'server_id'));
        clickHandlers[MCP_ACTION_SERVER_DELETE] = async (actionElement: HTMLElement) => dependencies.servers.deleteServer(dependencies.requireDataValue(actionElement, 'server_id'));
        clickHandlers[MCP_ACTION_SERVER_CONNECT] = async (actionElement: HTMLElement) => dependencies.connections.connectServer(actionElement, dependencies.requireDataValue(actionElement, 'server_id'));
        clickHandlers[MCP_ACTION_SERVER_DISCONNECT] = async (actionElement: HTMLElement) => dependencies.connections.disconnectServer(actionElement, dependencies.requireDataValue(actionElement, 'server_id'));
        clickHandlers[MCP_ACTION_SERVER_AUTHORIZE] = async (actionElement: HTMLElement) => dependencies.servers.authorizeServer(dependencies.requireDataValue(actionElement, 'server_id'));
        clickHandlers[MCP_ACTION_SERVER_CLEAR_AUTH] = async (actionElement: HTMLElement) => dependencies.servers.clearAuthorization(dependencies.requireDataValue(actionElement, 'server_id'));
        clickHandlers[MCP_ACTION_SEARCH_EDIT] = async (actionElement: HTMLElement) => dependencies.searchKeys.startSearchKeyEdit(dependencies.requireDataValue(actionElement, 'provider'));
        clickHandlers[MCP_ACTION_SEARCH_DELETE] = async (actionElement: HTMLElement) => dependencies.searchKeys.deleteSearchKey(dependencies.requireDataValue(actionElement, 'provider'));
        clickHandlers[MCP_ACTION_ROOT_CANCEL] = async () => dependencies.roots.cancelRootEdit();
        clickHandlers[MCP_ACTION_ROOT_EDIT] = async (actionElement: HTMLElement) => dependencies.roots.startRootEdit(dependencies.requireNonNegativeIndex(actionElement, 'index'));
        clickHandlers[MCP_ACTION_ROOT_DELETE] = async (actionElement: HTMLElement) => dependencies.roots.deleteRoot(dependencies.requireNonNegativeIndex(actionElement, 'index'));
        clickHandlers[MCP_ACTION_INTERACTION_RESOLVE] = async (actionElement: HTMLElement) => dependencies.interactions.resolveInteraction(actionElement, dependencies.requireDataValue(actionElement, 'task_id'));
    }

    const changeHandlers: Partial<Record<McpChangeActionId, (actionElement: HTMLElement) => Promise<void>>> = {};
    if (dependencies.isAdmin) {
        changeHandlers[MCP_ACTION_SERVER_ENABLED_CHANGE] = async (actionElement: HTMLElement) => {
            if (!(actionElement instanceof HTMLInputElement) || actionElement.type !== 'checkbox') {
                throw new TypeError(`MCP action ${MCP_ACTION_SERVER_ENABLED_CHANGE} requires a checkbox input`);
            }
            await dependencies.connections.toggleServerEnabled(actionElement, dependencies.requireDataValue(actionElement, 'server_id'));
        };
        changeHandlers[MCP_ACTION_SEARCH_PROVIDER_CHANGE] = async (actionElement: HTMLElement) => {
            const select = narrowSelect(actionElement, `MCP action ${MCP_ACTION_SEARCH_PROVIDER_CHANGE}`);
            dependencies.searchKeys.syncSearchProviderFields(select);
        };
        changeHandlers[MCP_ACTION_INTERACTION_ACTION_CHANGE] = async (actionElement: HTMLElement) => {
            const select = narrowSelect(actionElement, `MCP action ${MCP_ACTION_INTERACTION_ACTION_CHANGE}`);
            dependencies.interactions.updateInteractionButton(select);
        };
    }

    const actionController = new AbortController();
    bindDataActionListener({
        root: container,
        eventType: 'click',
        signal: actionController.signal,
        isAction: isMcpClickActionId,
        preventDefault: 'always',
        mouseButton: 'primary',
        ignoreDisabled: true,
        beforeEvent: (eventObject: Event): boolean => eventObject.defaultPrevented,
        onAction: async ({ action, actionElement, event }): Promise<void> => {
            const handler = clickHandlers[action];
            if (!handler) {
                throw new Error(`Missing MCP click handler for action: ${action}`);
            }
            await handler(actionElement, event);
        }
    });
    bindDataActionListener({
        root: container,
        eventType: 'change',
        signal: actionController.signal,
        isAction: isMcpChangeActionId,
        preventDefault: 'never',
        onAction: async ({ action, actionElement }): Promise<void> => {
            const handler = changeHandlers[action];
            if (!handler) {
                throw new Error(`Missing MCP change handler for action: ${action}`);
            }
            await handler(actionElement);
        }
    });
    cleanups.push(() => actionController.abort());
    if (dependencies.isAdmin) {
        const formController = new AbortController();
        const syncPendingFields = (eventObject: Event): void => {
            const target = eventObject.target;
            if (!(target instanceof HTMLElement)) {
                return;
            }
            if (target.id === 'mcp-root-uri-input' || target.id === 'mcp-root-name-input') {
                dependencies.roots.syncPendingFieldStates();
            }
            if (target.id === UI_IDS.MCP_SEARCH_PROVIDER_SELECT || target.id === 'mcp-search-provider-input' || target.id === 'mcp-search-api-key-input') {
                dependencies.searchKeys.syncPendingFieldStates();
            }
        };
        container.addEventListener('input', syncPendingFields, { signal: formController.signal, capture: true });
        container.addEventListener('change', syncPendingFields, { signal: formController.signal, capture: true });
        cleanups.push(() => formController.abort());
    }

    return cleanups;
};

export { bindMcpContainerHandlers };
export type { McpContainerHandlersDependencies, McpContainerHandlersHost };
