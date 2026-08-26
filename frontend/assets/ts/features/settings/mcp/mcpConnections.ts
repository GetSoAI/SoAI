/* SoAI - Settings feature MCP connections [frontend/assets/ts/features/settings/mcp/mcpConnections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';

type McpConnectionsHost = Pick<McpManagerHost, 'services' | 'view' | 'execution'>;

interface McpConnectionsDependencies {
    host: McpConnectionsHost;
    reload: () => Promise<boolean>;
}

class McpConnectionsManager {
    readonly #host: McpConnectionsHost;
    readonly #reload: () => Promise<boolean>;

    constructor({ host, reload }: McpConnectionsDependencies) {
        this.#host = host;
        this.#reload = reload;
    }

    async connectServer(button: Element, serverId: string): Promise<void> {
        await this.#host.execution.runWithBoundary('settings:connectMcpServer', async () => {
            await this.#host.execution.withButtonDisabled(button, async () => {
                await this.#host.services.api.mcp.servers.connect(serverId);
                this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverConnectSuccess'), 'success');
            });
            await this.#reload();
        });
    }

    async disconnectServer(button: Element, serverId: string): Promise<void> {
        await this.#host.execution.runWithBoundary('settings:disconnectMcpServer', async () => {
            await this.#host.execution.withButtonDisabled(button, async () => {
                await this.#host.services.api.mcp.servers.disconnect(serverId);
                this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverDisconnectSuccess'), 'success');
            });
            await this.#reload();
        });
    }

    async toggleServerEnabled(toggle: HTMLInputElement, serverId: string): Promise<void> {
        const nextEnabled = toggle.checked;
        const previousEnabled = toggle.getAttribute('data-enabled') === 'true';
        this.#host.view.updatePreferenceToggleLabel(toggle, nextEnabled);

        await this.#host.execution.runWithBoundary('settings:toggleMcpServer', async () => {
            const wasDisabled = toggle.disabled;
            try {
                setControlDisabledState(toggle, true);
                await this.#host.services.api.mcp.servers.update(serverId, { enabled: nextEnabled });
                toggle.setAttribute('data-enabled', nextEnabled ? 'true' : 'false');
                if (nextEnabled) {
                    this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverEnableSuccess'), 'success');
                } else {
                    this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverDisableSuccess'), 'success');
                }
            } catch (error) {
                toggle.checked = previousEnabled;
                this.#host.view.updatePreferenceToggleLabel(toggle, previousEnabled);
                const runtimeError = ensureError(error);
                if (error instanceof Error) {
                    throw runtimeError;
                }
                throw new Error(i18n.t('settings.mcp.notifications.serverToggleFailed'));
            } finally {
                setControlDisabledState(toggle, wasDisabled);
            }
        });
    }
}

export { McpConnectionsManager };
