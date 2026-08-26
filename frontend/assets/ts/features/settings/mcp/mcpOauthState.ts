/* SoAI - MCP OAuth settings state [frontend/assets/ts/features/settings/mcp/mcpOauthState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractUserFacingErrorMessage } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpOauthStartResponse } from '@core/mcp/contracts.ts';
import { isSettingsOauthStatus } from '@features/settings/oauthValues.ts';
import { resolveSettingsOauthFailureMessage, resolveSettingsOauthStatusLabel, type SettingsOauthStatusLabelCatalog } from '@features/settings/oauthStatusPresentation.ts';

type McpOauthStartResult = { kind: 'not_required' } | { kind: 'manual_required' } | { kind: 'redirect'; redirectUrl: string } | { kind: 'error'; diagnostic: string | null };

const getMcpOauthStatusLabels = (): SettingsOauthStatusLabelCatalog => ({
    ready: i18n.t('settings.mcp.servers.oauthStatus.ready'),
    none: i18n.t('settings.mcp.servers.oauthStatus.none'),
    authRequired: i18n.t('settings.mcp.servers.oauthStatus.auth_required'),
    insufficientScope: i18n.t('settings.mcp.servers.oauthStatus.insufficient_scope'),
    expired: i18n.t('settings.mcp.servers.oauthStatus.expired'),
    error: i18n.t('settings.mcp.servers.oauthStatus.error')
});

const resolveMcpOauthStatusLabel = (oauthStatus: string | null): string => {
    if (!isSettingsOauthStatus(oauthStatus)) {
        return i18n.t('settings.mcp.servers.oauthStatus.none');
    }
    return resolveSettingsOauthStatusLabel(oauthStatus, getMcpOauthStatusLabels()) ?? i18n.t('settings.mcp.servers.oauthStatus.none');
};

const resolveMcpOauthFailureMessage = (oauthStatus: string | null | undefined): string => {
    const normalizedStatus = isSettingsOauthStatus(oauthStatus) ? oauthStatus : null;
    return resolveSettingsOauthFailureMessage(i18n.t('settings.mcp.notifications.oauthFailed'), normalizedStatus, getMcpOauthStatusLabels());
};

const parseMcpOauthStartResult = (response: McpOauthStartResponse): McpOauthStartResult => {
    if (response.status === 'not_required') {
        return { kind: 'not_required' };
    }
    if (response.status === 'manual_required') {
        return { kind: 'manual_required' };
    }
    if (response.status === 'redirect') {
        return { kind: 'redirect', redirectUrl: response.redirectUrl };
    }
    return {
        kind: 'error',
        diagnostic: extractUserFacingErrorMessage(response.error)
    };
};

export { parseMcpOauthStartResult, resolveMcpOauthFailureMessage, resolveMcpOauthStatusLabel };
export type { McpOauthStartResult };
