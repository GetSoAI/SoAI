/* SoAI - MCP settings side effects [frontend/assets/ts/features/settings/mcp/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { MCP_SERVER_AUTH_OAUTH } from '@core/mcp/serverValues.ts';
import type { McpServerUpdatePayload } from '@core/mcp/contracts.ts';
import { validateMcpServerForm } from '@features/settings/mcp/mcpServerFormPayloadController.ts';
import { completeOauthServerSave } from '@features/settings/mcp/mcpOauthSaveFlow.ts';
import { buildMcpServerCreatePayload, buildMcpServerUpdates } from '@features/settings/mcp/mcpServerPayloads.ts';
import { isMcpServerOauthFlow } from '@features/settings/mcp/mcpServerFormRules.ts';
import { buildCreatedServerFromPayload, buildPartialCreateOrUpdateFailure, buildPersistedServerFromPayload, formatSaveResult, normalizeCreatedServerId, reloadAfterPartialSaveFailure, resolveNoChangePayloadMessage, requireReloadedPersistedServer, type McpServerModalSaveDependencies, type McpServerModalSaveOptions, type McpServerModalSaveResult } from '@features/settings/mcp/mcpServerModalSaveController.ts';

const performMcpServerModalSave = async (dependencies: McpServerModalSaveDependencies, options: McpServerModalSaveOptions = {}): Promise<McpServerModalSaveResult> => {
    const reloadAfterSave = options.reloadAfterSave !== false;
    const baselineAuthType = dependencies.server ? dependencies.server.authType : null;
    const payload = validateMcpServerForm(dependencies.formHost, dependencies.modalId, baselineAuthType);
    if (!payload) {
        return {
            changed: false,
            shouldClose: false,
            shouldReload: false,
            persistedServer: dependencies.server,
            finalMode: dependencies.mode
        };
    }

    const auth = payload.authType;
    const isOauth = isMcpServerOauthFlow(payload.transportType, auth);

    if (dependencies.mode === 'edit') {
        const server = dependencies.server;
        if (!server) {
            throw new Error('MCP server edit save requires an existing server');
        }
        const serverId = server.id;
        const nextServer = buildPersistedServerFromPayload(payload, serverId, server);

        const updates = buildMcpServerUpdates(payload, server);
        const hasPendingChanges = Object.keys(updates).length > 0;
        if (!hasPendingChanges) {
            dependencies.host.execution.feedback.show(resolveNoChangePayloadMessage(), 'info');
            return formatSaveResult({
                persistedServer: server,
                finalMode: 'edit',
                shouldClose: false,
                shouldReload: false,
                changed: false
            });
        }
        try {
            await dependencies.host.services.api.mcp.servers.update(serverId, updates);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('SettingsPage', 'MCP server update failed during save', runtimeError);
            return buildPartialCreateOrUpdateFailure(dependencies, server, { changed: false, shouldReload: false });
        }
        dependencies.host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverUpdateSuccess'), 'success');

        let persistedServer = nextServer;
        let reloadSucceeded = false;
        if (!payload.enabled) {
            if (reloadAfterSave) {
                reloadSucceeded = await dependencies.reload();
                if (reloadSucceeded) {
                    persistedServer = requireReloadedPersistedServer(dependencies, serverId);
                }
            }
            return formatSaveResult({
                persistedServer,
                finalMode: 'edit',
                shouldClose: !reloadAfterSave || reloadSucceeded,
                shouldReload: !reloadAfterSave || !reloadSucceeded,
                changed: true
            });
        }
        if (!isOauth) {
            try {
                await dependencies.host.services.api.mcp.servers.connect(serverId);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn('SettingsPage', 'MCP server connect failed after update', runtimeError);
                reloadSucceeded = await reloadAfterPartialSaveFailure(dependencies, reloadAfterSave, hasPendingChanges);
                if (reloadSucceeded) {
                    persistedServer = requireReloadedPersistedServer(dependencies, serverId);
                }
                return buildPartialCreateOrUpdateFailure(dependencies, persistedServer, {
                    changed: hasPendingChanges,
                    shouldReload: hasPendingChanges && !reloadSucceeded
                });
            }
            dependencies.host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverConnectSuccess'), 'success');
            if (reloadAfterSave && hasPendingChanges) {
                reloadSucceeded = await dependencies.reload();
                if (reloadSucceeded) {
                    persistedServer = requireReloadedPersistedServer(dependencies, serverId);
                }
            }
            return formatSaveResult({
                persistedServer,
                finalMode: 'edit',
                shouldClose: hasPendingChanges && (!reloadAfterSave || reloadSucceeded),
                shouldReload: hasPendingChanges && (!reloadAfterSave || !reloadSucceeded),
                changed: hasPendingChanges
            });
        }
        return completeOauthServerSave({
            dependencies,
            serverId,
            persistedServer: nextServer,
            reloadAfterSave,
            changedBeforeOauth: hasPendingChanges,
            startFailureLogMessage: 'MCP server OAuth start failed after update',
            popupFailureLogMessage: 'MCP server OAuth popup flow failed after update'
        });
    }

    const createPayload = buildMcpServerCreatePayload(payload);
    const response = await dependencies.host.services.api.mcp.servers.create(createPayload);
    const createdId = normalizeCreatedServerId(response);
    let createdServer = buildCreatedServerFromPayload(payload, createdId);

    const postCreateUpdates: McpServerUpdatePayload = {};
    if (isOauth) {
        postCreateUpdates.authType = MCP_SERVER_AUTH_OAUTH;
        if (payload.oauthClientId) {
            postCreateUpdates.oauthClientId = payload.oauthClientId;
        }
        if (payload.oauthClientSecret) {
            postCreateUpdates.oauthClientSecret = payload.oauthClientSecret;
        }
    }
    if (!payload.enabled) {
        postCreateUpdates.enabled = false;
    }

    if (Object.keys(postCreateUpdates).length > 0) {
        try {
            await dependencies.host.services.api.mcp.servers.update(createdId, postCreateUpdates);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('SettingsPage', 'MCP server create update step failed', runtimeError);
            const reloadSucceeded = await reloadAfterPartialSaveFailure(dependencies, reloadAfterSave, true);
            const persistedServer = reloadSucceeded ? requireReloadedPersistedServer(dependencies, createdId) : createdServer;
            return buildPartialCreateOrUpdateFailure(dependencies, persistedServer, {
                changed: true,
                shouldReload: !reloadSucceeded
            });
        }
        createdServer = buildPersistedServerFromPayload(payload, createdId, createdServer);
    }
    dependencies.host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverCreateSuccess'), 'success');

    if (!payload.enabled) {
        let reloadSucceeded = false;
        if (reloadAfterSave) {
            reloadSucceeded = await dependencies.reload();
            if (reloadSucceeded) {
                createdServer = requireReloadedPersistedServer(dependencies, createdId);
            }
        }
        return formatSaveResult({
            persistedServer: createdServer,
            finalMode: 'edit',
            shouldClose: !reloadAfterSave || reloadSucceeded,
            shouldReload: !reloadAfterSave || !reloadSucceeded,
            changed: true
        });
    }

    if (!isOauth) {
        try {
            await dependencies.host.services.api.mcp.servers.connect(createdId);
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('SettingsPage', 'MCP server connect failed after creation', runtimeError);
            const reloadSucceeded = await reloadAfterPartialSaveFailure(dependencies, reloadAfterSave, true);
            const persistedServer = reloadSucceeded ? requireReloadedPersistedServer(dependencies, createdId) : createdServer;
            return buildPartialCreateOrUpdateFailure(dependencies, persistedServer, {
                changed: true,
                shouldReload: !reloadSucceeded
            });
        }
        dependencies.host.execution.feedback.show(i18n.t('settings.mcp.notifications.serverConnectSuccess'), 'success');
        let reloadSucceeded = false;
        if (reloadAfterSave) {
            reloadSucceeded = await dependencies.reload();
            if (reloadSucceeded) {
                createdServer = requireReloadedPersistedServer(dependencies, createdId);
            }
        }
        return formatSaveResult({
            persistedServer: createdServer,
            finalMode: 'edit',
            shouldClose: !reloadAfterSave || reloadSucceeded,
            shouldReload: !reloadAfterSave || !reloadSucceeded,
            changed: true
        });
    }

    return completeOauthServerSave({
        dependencies,
        serverId: createdId,
        persistedServer: createdServer,
        reloadAfterSave,
        changedBeforeOauth: true,
        startFailureLogMessage: 'MCP server OAuth start failed after creation',
        popupFailureLogMessage: 'MCP server OAuth popup flow failed after creation'
    });
};

export { performMcpServerModalSave };
export type { McpServerModalSaveResult, McpServerModalSaveDependencies, McpServerModalSaveOptions };
