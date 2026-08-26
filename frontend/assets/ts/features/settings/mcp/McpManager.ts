/* SoAI - MCP settings feature manager [frontend/assets/ts/features/settings/mcp/McpManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { requireNonNegativeIntegerDataAttribute, requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderSettingsSection } from '@core/settings/settingsSectionRuntime.ts';
import { SettingsSectionLifecycle } from '@features/settings/sectionLifecycle.ts';
import { createSettingsCapabilityAvailability, markSettingsCapabilityFailed, markSettingsCapabilityReady, renderSettingsCapabilityNotice, settleSettingsCapability, type SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';
import { McpAccessTokensManager } from '@features/settings/mcp/mcpAccessTokens.ts';
import { McpConnectionsManager } from '@features/settings/mcp/mcpConnections.ts';
import { bindMcpContainerHandlers } from '@features/settings/mcp/mcpContainerHandlersController.ts';
import { syncMcpFormDefaultsToCurrent } from '@features/settings/mcp/mcpFormDefaultsSyncController.ts';
import { McpInteractionsManager } from '@features/settings/mcp/mcpInteractions.ts';
import type { McpManagerDependencies, McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import { bindMcpRealtime } from '@features/settings/mcp/mcpRealtimeController.ts';
import { McpRootsManager } from '@features/settings/mcp/mcpRoots.ts';
import { createMcpSaveCoordinator, type McpSaveCoordinator } from '@features/settings/mcp/mcpSaveCoordinatorController.ts';
import { McpSearchKeysManager } from '@features/settings/mcp/mcpSearchKeys.ts';
import { createMcpSectionExpansionState, type McpSectionExpansionState } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { McpServersManager } from '@features/settings/mcp/mcpServers.ts';
import { renderMcpConfigSubgroup } from '@features/settings/mcp/renderConfigSection.ts';
import { renderMcpConnectionsSubgroup } from '@features/settings/mcp/renderConnectionsSection.ts';
import { renderMcpPromptsSubgroup, renderMcpResourcesSubgroup, renderMcpToolsSubgroup } from '@features/settings/mcp/renderResourcesToolsPromptsSections.ts';
import { renderMcpServersSubgroup } from '@features/settings/mcp/renderServersSection.ts';
import { renderMcpStatusSubgroup } from '@features/settings/mcp/renderStatusSection.ts';
import { applyMcpManagerData, collectMcpManagerFailures, countMcpManagerSuccesses, fetchMcpManagerData } from '@features/settings/mcp/service.ts';

const MCP_CONTAINER_ID = 'mcp-content';
const MCP_CONTAINER_CLEANUP_GROUP = 'mcp-container-listeners';
const MCP_CONTAINER_CLEANUP_ERROR = 'MCP container listener cleanup failed';
class McpManager {
    readonly #host: McpManagerHost;
    readonly #servers: McpServersManager;
    readonly #connections: McpConnectionsManager;
    readonly #searchKeys: McpSearchKeysManager;
    readonly #roots: McpRootsManager;
    readonly #interactions: McpInteractionsManager;
    readonly #accessTokens: McpAccessTokensManager;
    readonly #saveCoordinator: McpSaveCoordinator;
    readonly #sectionExpansion: McpSectionExpansionState;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();
    #availability: SettingsCapabilityAvailability = createSettingsCapabilityAvailability();
    constructor({ host }: McpManagerDependencies) {
        if (!host) {
            throw new Error('McpManager requires a host instance');
        }
        this.#host = host;
        this.#sectionExpansion = createMcpSectionExpansionState();
        const rerender = (): void => {
            this.#renderIntoContainer();
        };
        const reload = this.reload;
        this.#servers = new McpServersManager({ host, reload });
        this.#connections = new McpConnectionsManager({ host, reload });
        this.#searchKeys = new McpSearchKeysManager({ host, reload });
        this.#roots = new McpRootsManager({ host, reload, rerender });
        this.#interactions = new McpInteractionsManager({ host, reload });
        this.#accessTokens = new McpAccessTokensManager({ host, reload });
        this.#saveCoordinator = createMcpSaveCoordinator({ servers: this.#servers, roots: this.#roots, searchKeys: this.#searchKeys, reload });
    }

    hasPendingChanges(): boolean {
        return this.#saveCoordinator.hasChanges();
    }

    arePendingChangesValid(): boolean {
        return this.#saveCoordinator.arePendingChangesValid();
    }

    async savePendingChanges(): Promise<void> {
        await this.#saveCoordinator.savePendingChanges();
    }
    async openCreateServerModal(): Promise<void> {
        await this.#servers.openCreateModal();
    }
    render(): TrustedHtml {
        const resolveExpanded = this.#sectionExpansion.resolve;
        const configSection = this.#host.data.canPatchCoreConfig() ? renderMcpConfigSubgroup(this.#host, resolveExpanded) : '';
        const sections = renderMcpStatusSubgroup(this.#host) + this.#accessTokens.renderSubgroup(resolveExpanded) + configSection + renderMcpServersSubgroup(this.#host, resolveExpanded) + renderMcpConnectionsSubgroup(this.#host, resolveExpanded) + this.#interactions.renderSubgroup(resolveExpanded) + renderMcpResourcesSubgroup(this.#host, resolveExpanded) + renderMcpPromptsSubgroup(this.#host, resolveExpanded) + renderMcpToolsSubgroup(this.#host, resolveExpanded) + this.#searchKeys.renderSubgroup(resolveExpanded) + this.#roots.renderSubgroup(resolveExpanded);
        return toTrustedUiHtml(`${renderSettingsCapabilityNotice(this.#availability)}<div class="settings-mcp-grid mcp-tools-scope">${sections}</div>`);
    }
    setupEventListeners(): void {
        this.dispose();
        this.#lifecycle.mount();
        this.#bindContainerHandlers();
        if (this.#host.services.isAdmin()) {
            this.#lifecycle.addCleanup(bindMcpRealtime(this.#host, async () => this.reload()));
        }
    }
    readonly reload = async (): Promise<boolean> => {
        const reloadRun = this.#lifecycle.beginReload('mcp-reload');
        if (reloadRun === null) {
            return false;
        }
        try {
            const accessTokensResult = settleSettingsCapability(() => this.#accessTokens.reload());
            let successfulCapabilities = 0;
            const failures: Error[] = [];
            if (this.#host.services.isAdmin()) {
                const [tokens, data] = await Promise.all([accessTokensResult, fetchMcpManagerData(this.#host)]);
                if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                    return false;
                }
                applyMcpManagerData(this.#host, data);
                successfulCapabilities = countMcpManagerSuccesses(data) + (tokens.succeeded ? 1 : 0);
                failures.push(...collectMcpManagerFailures(data));
                if (!tokens.succeeded && tokens.error) failures.push(tokens.error);
            } else {
                const tokens = await accessTokensResult;
                successfulCapabilities = tokens.succeeded ? 1 : 0;
                if (!tokens.succeeded && tokens.error) failures.push(tokens.error);
            }
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return false;
            }
            const expectedCapabilities = this.#host.services.isAdmin() ? 10 : 1;
            this.#availability = failures.length === 0 ? markSettingsCapabilityReady() : markSettingsCapabilityFailed(this.#availability, successfulCapabilities > 0);
            for (const failure of failures) {
                this.#host.execution.feedback.handle(failure, 'MCP manager capability reload', { severity: 'warn' });
            }
            this.#renderIntoContainer();
            if (successfulCapabilities !== expectedCapabilities) {
                this.#host.execution.feedback.show(i18n.t('settings.mcp.errors.reloadFailed'), 'error');
                return false;
            }
            return true;
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return false;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('McpManager', 'MCP manager reload failed', runtimeError);
            this.#host.execution.feedback.show(i18n.t('settings.mcp.errors.reloadFailed'), 'error');
            return false;
        }
    };
    dispose(): void {
        this.#lifecycle.dispose('mcp-dispose');
    }
    #renderIntoContainer(): void {
        if (!this.#lifecycle.isMounted) {
            return;
        }
        renderSettingsSection({
            container: this.#requireContainer(),
            render: () => this.render(),
            renderMarkup: (container, markup): void => this.#host.view.pageDom.updateHtml(container, markup),
            afterRender: (): void => this.#host.editing.rebindConfigForm(),
            bind: (): void => this.#bindContainerHandlers(),
            filter: (): void => this.#host.services.filterSettings(),
            hasSearchQuery: (): boolean => this.#host.services.hasSearchQuery()
        });
    }
    #bindContainerHandlers(): void {
        const container = this.#requireContainer();
        this.#lifecycle.replaceCleanupGroup(
            MCP_CONTAINER_CLEANUP_GROUP,
            () =>
                bindMcpContainerHandlers({
                    host: this.#host,
                    container,
                    isAdmin: this.#host.services.isAdmin(),
                    reload: async () => this.reload(),
                    accessTokens: this.#accessTokens,
                    servers: this.#servers,
                    connections: this.#connections,
                    searchKeys: this.#searchKeys,
                    roots: this.#roots,
                    interactions: this.#interactions,
                    persistSectionExpansion: (sectionId, expanded) => this.#sectionExpansion.set(sectionId, expanded),
                    requireDataValue: (element: Element, key: string) => this.#requireDataValue(element, key),
                    requireNonNegativeIndex: (element: Element, key: string) => this.#requireNonNegativeIndex(element, key)
                }),
            MCP_CONTAINER_CLEANUP_ERROR
        );
        syncMcpFormDefaultsToCurrent(container);
        if (this.#host.services.isAdmin()) {
            this.#searchKeys.syncPendingFieldStates();
            this.#roots.syncPendingFieldStates();
        }
        this.#host.execution.notifySaveChanged();
    }
    #requireContainer(): HTMLElement {
        return this.#host.view.pageDom.requireHTMLElement(MCP_CONTAINER_ID);
    }
    #requireDataValue(element: Element, key: string): string {
        return requireTrimmedDataAttribute(element, key, 'MCP action element');
    }
    #requireNonNegativeIndex(element: Element, key: string): number {
        return requireNonNegativeIntegerDataAttribute(element, key, 'MCP action element');
    }
}
export { McpManager };
