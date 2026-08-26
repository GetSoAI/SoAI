/* SoAI - MCP server modal save result helpers [frontend/assets/ts/features/settings/mcp/mcpServerModalSaveController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { McpServer, McpServerCreateResponse } from '@core/mcp/contracts.ts';
import { setStatusSurface } from '@core/ui/statusSurface.ts';
import type { McpServerFormData } from '@features/settings/mcp/mcpManagerTypes.ts';
import { isMcpServerOauthAuth, isMcpServerOauthFlow, resolveCreatedMcpServerAuthType } from '@features/settings/mcp/mcpServerFormRules.ts';
import { buildMcpServerFormBaseline } from '@features/settings/mcp/mcpServerPayloads.ts';
import type { McpServerFormHost } from '@features/settings/mcp/mcpServerFormSnapshot.ts';
import type { McpServersHost } from '@features/settings/mcp/types.ts';

type McpServerModalMode = 'create' | 'edit';

type McpServerModalSaveDependencies = {
    host: McpServersHost;
    modalId: string;
    mode: McpServerModalMode;
    server: McpServer | null;
    reload: () => Promise<boolean>;
    formHost: McpServerFormHost;
    summary: HTMLElement;
    oauthManualSection: HTMLElement;
    oauthClientIdInput: HTMLInputElement;
};

type McpServerModalSaveResult = {
    changed: boolean;
    shouldClose: boolean;
    shouldReload: boolean;
    persistedServer: McpServer | null;
    finalMode: McpServerModalMode;
};

type McpServerModalSaveOptions = {
    reloadAfterSave?: boolean | undefined;
};

const reloadAfterPartialSaveFailure = async (dependencies: Pick<McpServerModalSaveDependencies, 'reload'>, reloadAfterSave: boolean, changed: boolean): Promise<boolean> => {
    if (!reloadAfterSave || !changed) {
        return false;
    }
    return dependencies.reload();
};

const requireReloadedPersistedServer = (dependencies: Pick<McpServerModalSaveDependencies, 'host'>, serverId: string): McpServer => {
    const server = dependencies.host.data.getMcpData().servers.find((entry) => entry.id === serverId) ?? null;
    if (server === null) {
        throw new Error('MCP server reload did not include the persisted server');
    }
    return server;
};

const normalizeCreatedServerId = (response: McpServerCreateResponse): string => response.id;

const buildPersistedServerFromPayload = (payload: McpServerFormData, serverId: string, existing: McpServer | null): McpServer => {
    const existingAuthType = existing?.authType ?? null;
    const isOauth = isMcpServerOauthFlow(payload.transportType, payload.authType);
    const hadOauthAuth = isMcpServerOauthAuth(existingAuthType);
    return buildMcpServerFormBaseline(payload, serverId, {
        status: existing?.status ?? null,
        apiKeyMasked: existing?.apiKeyMasked ?? null,
        oauthStatus: isOauth ? (existing?.oauthStatus ?? null) : null,
        oauthHasClientSecret: isOauth ? (payload.oauthClientSecret !== null ? true : hadOauthAuth ? (existing?.oauthHasClientSecret ?? false) : false) : false,
        oauthHasAccessToken: isOauth ? (hadOauthAuth ? (existing?.oauthHasAccessToken ?? false) : false) : false,
        oauthHasRefreshToken: isOauth ? (hadOauthAuth ? (existing?.oauthHasRefreshToken ?? false) : false) : false,
        oauthExpiresAtMs: isOauth ? (existing?.oauthExpiresAtMs ?? null) : null,
        oauthScopes: isOauth ? (existing?.oauthScopes ?? null) : null,
        oauthRequiredScopes: isOauth ? (existing?.oauthRequiredScopes ?? null) : null,
        createdAtMs: existing?.createdAtMs ?? null,
        lastModifiedAtMs: existing?.lastModifiedAtMs ?? null,
        lastError: existing?.lastError ?? null
    });
};

const buildCreatedServerFromPayload = (payload: McpServerFormData, serverId: string): McpServer => {
    const createdAuthType = resolveCreatedMcpServerAuthType(payload.authType, payload.apiKey);
    return buildMcpServerFormBaseline(
        {
            ...payload,
            authType: createdAuthType,
            enabled: true,
            oauthClientId: null,
            oauthClientSecret: null
        },
        serverId,
        {
            status: 'disconnected',
            apiKeyMasked: null,
            oauthStatus: null,
            oauthHasClientSecret: false,
            oauthHasAccessToken: false,
            oauthHasRefreshToken: false,
            oauthExpiresAtMs: null,
            oauthScopes: null,
            oauthRequiredScopes: null,
            createdAtMs: null,
            lastModifiedAtMs: null,
            lastError: null
        }
    );
};

const resolveNoChangePayloadMessage = (): string => i18n.t('settings.mcp.notifications.serverNoChanges');

const formatSaveResult = (inputArguments: { persistedServer: McpServer; finalMode: McpServerModalMode; shouldClose: boolean; shouldReload: boolean; changed: boolean }): McpServerModalSaveResult => {
    return {
        changed: inputArguments.changed,
        shouldClose: inputArguments.shouldClose,
        shouldReload: inputArguments.shouldReload,
        persistedServer: inputArguments.persistedServer,
        finalMode: inputArguments.finalMode
    };
};

const buildPartialCreateOrUpdateFailure = (dependencies: McpServerModalSaveDependencies, persistedServer: McpServer, inputArguments: { changed: boolean; shouldReload: boolean }): McpServerModalSaveResult => {
    const message = i18n.t('settings.mcp.notifications.serverSaveFailed');
    dependencies.host.execution.feedback.show(message, 'error');
    setStatusSurface({
        surface: dependencies.summary,
        message
    });
    return formatSaveResult({
        persistedServer,
        finalMode: 'edit',
        shouldClose: false,
        shouldReload: inputArguments.shouldReload,
        changed: inputArguments.changed
    });
};

export type { McpServerModalMode, McpServerModalSaveDependencies, McpServerModalSaveOptions, McpServerModalSaveResult };
export { buildCreatedServerFromPayload, buildPartialCreateOrUpdateFailure, buildPersistedServerFromPayload, formatSaveResult, normalizeCreatedServerId, reloadAfterPartialSaveFailure, resolveNoChangePayloadMessage, requireReloadedPersistedServer };
