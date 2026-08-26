/* SoAI - MCP server manager actions [frontend/assets/ts/features/settings/mcp/mcpServers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { SETTINGS_MCP_SERVER_MODAL_ID } from '@features/settings/mcp/constants.ts';
import { performMcpServerModalSave } from '@features/settings/mcp/effects.ts';
import { syncMcpFormDefaultsToCurrent } from '@features/settings/mcp/mcpFormDefaultsSyncController.ts';
import { parseMcpOauthStartResult, resolveMcpOauthFailureMessage } from '@features/settings/mcp/mcpOauthState.ts';
import { hasMcpServerFormPendingChanges, isMcpServerFormPendingChangesValid } from '@features/settings/mcp/mcpServerFormPendingController.ts';
import { resolveRequiredMcpServerFormFields, type McpServerFormHost } from '@features/settings/mcp/mcpServerFormSnapshot.ts';
import { MCP_SERVER_MODAL_DRAFT_ID, openMcpServerModal } from '@features/settings/mcp/mcpServerModal.ts';
import type { McpServersHost } from '@features/settings/mcp/types.ts';
import { openOauthPopupAndWait } from '@features/settings/oauthPopupFlowController.ts';

interface McpServersDependencies {
    host: McpServersHost;
    reload: () => Promise<boolean>;
}

type McpServerSaveOptions = {
    reloadAfterSave?: boolean | undefined;
};

class McpServersManager {
    readonly #host: McpServersHost;
    readonly #reload: () => Promise<boolean>;

    constructor({ host, reload }: McpServersDependencies) {
        this.#host = host;
        this.#reload = reload;
    }

    hasPendingChanges(): boolean {
        if (!this.#host.editing.getMcpServerEditId()) {
            return false;
        }
        return hasMcpServerFormPendingChanges(this.#host.view, SETTINGS_MCP_SERVER_MODAL_ID);
    }

    isPendingChangesValid(): boolean {
        if (!this.#hasPendingSession()) {
            return true;
        }
        return isMcpServerFormPendingChangesValid(this.#host.view, SETTINGS_MCP_SERVER_MODAL_ID, this.#host.editing.getMcpServerEditBaseline()?.authType ?? null);
    }

    validatePendingChanges(): boolean {
        if (!this.#hasPendingSession()) {
            return true;
        }
        return this.isPendingChangesValid();
    }

    async saveServer(options: McpServerSaveOptions = {}): Promise<boolean> {
        let shouldReload = false;
        await this.#host.execution.runWithBoundary('settings:saveMcpServer', async () => {
            if (!this.#hasPendingSession()) {
                return;
            }

            const modal = this.#host.view.pageDom.optional(`#${SETTINGS_MCP_SERVER_MODAL_ID}`);
            if (!(modal instanceof HTMLElement)) {
                throw new Error('MCP server modal is required for pending save');
            }

            const formHost: McpServerFormHost = {
                pageDom: this.#host.view.pageDom,
                formRoot: modal,
                resolver: createModalElementResolver(modal, 'MCP server modal'),
                warnAndFocus: this.#host.view.warnAndFocus
            };
            const requireOAuthClientIdInput = (): HTMLInputElement => {
                const element = resolveRequiredMcpServerFormFields(formHost, SETTINGS_MCP_SERVER_MODAL_ID).oauthClientIdInput;
                if (!element) {
                    throw new Error('MCP OAuth client-id input is required');
                }
                return element;
            };

            const persistedMode = this.#host.editing.getMcpServerEditId() === MCP_SERVER_MODAL_DRAFT_ID ? 'create' : 'edit';
            const result = await performMcpServerModalSave(
                {
                    host: this.#host,
                    modalId: SETTINGS_MCP_SERVER_MODAL_ID,
                    mode: persistedMode,
                    server: this.#host.editing.getMcpServerEditBaseline(),
                    reload: this.#reload,
                    formHost,
                    summary: this.#host.view.pageDom.requireHTMLElement(modalUiSelector(SETTINGS_MCP_SERVER_MODAL_ID, 'summary'), modal),
                    oauthManualSection: this.#host.view.pageDom.requireHTMLElement(modalUiSelector(SETTINGS_MCP_SERVER_MODAL_ID, 'oauth-manual-client'), modal),
                    oauthClientIdInput: requireOAuthClientIdInput()
                },
                { reloadAfterSave: options.reloadAfterSave }
            );

            if (result.persistedServer) {
                if (result.finalMode === 'edit') {
                    this.#host.editing.setMcpServerEditId(result.persistedServer.id);
                } else {
                    this.#host.editing.setMcpServerEditId(MCP_SERVER_MODAL_DRAFT_ID);
                }
                this.#host.editing.setMcpServerEditBaseline(result.persistedServer);
                syncMcpFormDefaultsToCurrent(modal, { modalId: SETTINGS_MCP_SERVER_MODAL_ID });
            }
            if (result.shouldClose) {
                requireModalPresenter().close(SETTINGS_MCP_SERVER_MODAL_ID, { force: true });
            }
            shouldReload = shouldReload || result.shouldReload;
        });
        return shouldReload;
    }

    async openCreateModal(): Promise<void> {
        await this.#host.execution.runWithBoundary('settings:openMcpServerCreateModal', async () => {
            await openMcpServerModal(this.#host, {
                mode: 'create',
                server: null,
                revealManualOauthClient: false,
                reload: this.#reload
            });
        });
    }

    async openEditModal(serverId: string, options: { revealManualOauthClient?: boolean } = {}): Promise<void> {
        await this.#host.execution.runWithBoundary('settings:openMcpServerEditModal', async () => {
            const server = this.#host.data.getMcpData().servers.find((entry) => entry.id === serverId) ?? null;
            if (!server) {
                this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverNotFound'), 'error');
                return;
            }
            await openMcpServerModal(this.#host, {
                mode: 'edit',
                server,
                revealManualOauthClient: options.revealManualOauthClient === true,
                reload: this.#reload
            });
        });
    }

    async authorizeServer(serverId: string): Promise<void> {
        await this.#host.execution.runWithBoundary('settings:authorizeMcpServer', async () => {
            let shouldOpenManualOauthModal = false;
            try {
                const result = await this.#startOauth(serverId);
                shouldOpenManualOauthModal = result === 'manual_required';
            } finally {
                await this.#reload();
            }
            if (shouldOpenManualOauthModal) {
                await this.openEditModal(serverId, { revealManualOauthClient: true });
            }
        });
    }

    async clearAuthorization(serverId: string): Promise<void> {
        await this.#host.execution.confirmAndExecute(
            'settings:clearMcpServerAuthorization',
            {
                title: i18n.t('settings.mcp.confirmClearAuthorization.title'),
                message: i18n.t('settings.mcp.confirmClearAuthorization.message'),
                confirmText: i18n.t('settings.mcp.servers.actions.clearAuth'),
                cancelText: i18n.t('common.cancel'),
                variant: 'danger'
            },
            () => this.#host.services.api.mcp.oauth.clear(serverId),
            i18n.t('settings.mcp.notifications.oauthCleared'),
            async () => {
                await this.#reload();
            },
            null
        );
    }

    async deleteServer(serverId: string): Promise<void> {
        await this.#host.execution.confirmAndExecute(
            'settings:deleteMcpServer',
            {
                title: i18n.t('settings.mcp.confirmDeleteServer.title'),
                message: i18n.t('settings.mcp.confirmDeleteServer.message'),
                confirmText: i18n.t('settings.mcp.servers.actions.delete'),
                cancelText: i18n.t('common.cancel'),
                variant: 'danger'
            },
            () => this.#host.services.api.mcp.servers.delete(serverId),
            i18n.t('settings.mcp.notifications.serverDeleteSuccess'),
            async () => {
                await this.#reload();
            },
            null
        );
    }

    async #startOauth(serverId: string): Promise<'completed' | 'manual_required'> {
        const resultRaw = await this.#host.services.api.mcp.oauth.start(serverId);
        const result = parseMcpOauthStartResult(resultRaw);
        if (result.kind === 'not_required') {
            this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.oauthNotRequired'), 'info');
            return 'completed';
        }
        if (result.kind === 'manual_required') {
            this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.oauthManualRequired'), 'warning');
            return 'manual_required';
        }
        if (result.kind === 'redirect') {
            const payload = await openOauthPopupAndWait({
                redirectUrl: result.redirectUrl,
                pollStatus: async () => (await this.#host.services.api.mcp.oauth.status(serverId)).oauthStatus,
                logContext: 'McpServersManager',
                startFailureMessage: i18n.t('settings.mcp.notifications.oauthFailed'),
                statusFailureMessage: i18n.t('settings.mcp.notifications.oauthFailed')
            });
            if (payload.ok) {
                this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.oauthAuthorized'), 'success');
                return 'completed';
            }
            this.#host.execution.feedback.show(resolveMcpOauthFailureMessage(payload.oauthStatus), 'error');
            return 'completed';
        }
        if (result.diagnostic) {
            errorHandler.warn('McpServersManager', 'MCP OAuth start was rejected', { diagnostic: result.diagnostic });
        }
        this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.oauthFailed'), 'error');
        return 'completed';
    }

    #hasPendingSession(): boolean {
        return this.#host.editing.getMcpServerEditId() !== null;
    }
}

export { McpServersManager };
