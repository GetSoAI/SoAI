/* SoAI - Settings feature MCP access tokens [frontend/assets/ts/features/settings/mcp/mcpAccessTokens.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatPositiveEpochMsSecondWithFallback } from '@core/primitives/dateTime.ts';
import { daysToMs } from '@core/time/durations.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { renderSettingsRecordList } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarAddButton } from '@core/settings/titlebarActions.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import { MCP_ACTION_ACCESS_TOKEN_CREATE, MCP_ACTION_ACCESS_TOKEN_REVOKE } from '@features/settings/mcp/actions.ts';
import type { McpAccessTokenRecord } from '@core/api/contracts/mcpAccessTokenContracts.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';
import { showMcpAccessTokenCreateExpiryModal, showMcpAccessTokenCreateLabelModal, showMcpAccessTokenSecretModal } from '@features/settings/tokenflow/definitions.ts';
import { resolveSettingsTokenBadgeClass, resolveSettingsTokenItemStateClass, resolveSettingsTokenStatus, resolveSettingsTokenStatusLabel } from '@features/settings/tokenflow/tokenListView.ts';

type McpAccessTokensManagerHost = Pick<McpManagerHost, 'services' | 'execution'>;

const MCP_ACCESS_TOKEN_EXPIRY_MS = daysToMs(90);

type McpAccessTokensManagerDependencies = {
    host: McpAccessTokensManagerHost;
    reload: () => Promise<boolean>;
};

class McpAccessTokensManager {
    readonly #host: McpAccessTokensManagerHost;
    readonly #reload: () => Promise<boolean>;
    #tokens: McpAccessTokenRecord[] = [];
    #createFlowInFlight: boolean = false;

    constructor({ host, reload }: McpAccessTokensManagerDependencies) {
        this.#host = host;
        this.#reload = reload;
    }

    async reload(): Promise<void> {
        const host = this.#host;
        const response = await host.services.api.webui.mcpAccessTokens.list();
        this.#tokens = response.tokens;
    }

    renderSubgroup(resolveExpanded: McpSectionExpansionResolver): string {
        const createLabel = i18n.t('settings.mcp.tokens.create.action.button');
        const createButton = renderSettingsTitlebarAddButton({ id: UI_IDS.MCP_ACCESS_TOKEN_CREATE, action: MCP_ACTION_ACCESS_TOKEN_CREATE, label: createLabel });
        return renderMcpCollapsibleSection({
            id: 'tokens',
            title: i18n.t('settings.mcp.tokens.title'),
            description: i18n.t('settings.mcp.tokens.description'),
            trailing: createButton,
            className: 'settings-section--mcp settings-section--mcp-tokens',
            content: this.#renderTokenList(),
            expanded: true,
            resolveExpanded
        });
    }

    async openCreateFlow(): Promise<void> {
        if (this.#createFlowInFlight) {
            return;
        }
        this.#createFlowInFlight = true;
        try {
            const host = this.#host;
            let normalizedLabel = '';
            const initialLabel = await showMcpAccessTokenCreateLabelModal(normalizedLabel);
            if (initialLabel === null) {
                return;
            }
            normalizedLabel = initialLabel;
            let expiryChoice = await showMcpAccessTokenCreateExpiryModal();
            while (expiryChoice === 'back') {
                const nextLabel = await showMcpAccessTokenCreateLabelModal(normalizedLabel);
                if (nextLabel === null) {
                    return;
                }
                normalizedLabel = nextLabel;
                expiryChoice = await showMcpAccessTokenCreateExpiryModal();
            }
            if (expiryChoice === null) {
                return;
            }
            const expiresAtMs = expiryChoice === '90days' ? serverEpochMs() + MCP_ACCESS_TOKEN_EXPIRY_MS : null;
            await host.execution.runWithBoundary('settings:mcpAccessTokens:create', async (): Promise<void> => {
                const createdRaw = await host.services.api.webui.mcpAccessTokens.create({
                    label: normalizedLabel,
                    expiresAtMs: expiresAtMs
                });
                await showMcpAccessTokenSecretModal(createdRaw.token);
                host.execution.feedback.show(i18n.t('settings.mcp.tokens.notifications.created'), 'success');
                await this.#reload();
            });
        } finally {
            this.#createFlowInFlight = false;
        }
    }

    async revokeToken(tokenId: string, onReload: () => Promise<boolean>): Promise<void> {
        const host = this.#host;
        await host.execution.confirmAndExecute(
            'settings:mcpAccessTokens:revoke',
            {
                title: i18n.t('settings.mcp.tokens.confirmRevoke.title'),
                message: i18n.t('settings.mcp.tokens.confirmRevoke.message'),
                confirmText: i18n.t('settings.mcp.tokens.actions.revoke'),
                cancelText: i18n.t('common.cancel'),
                variant: 'warning'
            },
            () => host.services.api.webui.mcpAccessTokens.revoke(tokenId),
            i18n.t('settings.mcp.tokens.notifications.revoked'),
            async () => {
                await onReload();
            },
            null
        );
    }

    #renderTokenItem(token: McpAccessTokenRecord): string {
        const sanitizer = this.#host.services.pageContext.sanitizer;
        const status = resolveSettingsTokenStatus(token.revoked, token.expiresAtMs);
        const itemStateClass = resolveSettingsTokenItemStateClass(status);
        const badgeStateClass = resolveSettingsTokenBadgeClass(status);
        const createdText = this.#formatTimestamp(token.createdAtMs);
        const lastUsedText = token.lastUsedAtMs ? this.#formatTimestamp(token.lastUsedAtMs) : i18n.t('settings.mcp.tokens.list.never');
        const expiresText = token.expiresAtMs ? this.#formatTimestamp(token.expiresAtMs) : i18n.t('settings.mcp.tokens.list.never');
        const badgeLabel = resolveSettingsTokenStatusLabel(status, {
            active: i18n.t('settings.mcp.tokens.list.active'),
            revoked: i18n.t('settings.mcp.tokens.list.revoked'),
            expired: i18n.t('settings.mcp.tokens.list.expired')
        });
        const actions = token.revoked ? '' : this.#renderRevokeAction(token);

        return `<div class="settings-record-item mcp-token-item ${itemStateClass}"><div class="settings-record-info api-key-info"><div class="settings-record-header api-key-header"><span class="settings-record-label api-key-label">${sanitizer.html(token.label)}</span><span class="settings-record-badge settings-record-badge--${badgeStateClass}">${badgeLabel}</span></div><div class="api-key-prefix"><code>${sanitizer.html(token.prefix)}...</code></div><div class="settings-record-meta api-key-meta"><span>${i18n.t('settings.apiKeys.keyItem.created')}: ${createdText}</span><span>${i18n.t('settings.apiKeys.keyItem.last_used')}: ${lastUsedText}</span><span>${i18n.t('settings.apiKeys.keyItem.expires')}: ${expiresText}</span></div></div>${actions}</div>`;
    }

    #renderRevokeAction(token: McpAccessTokenRecord): string {
        const sanitizer = this.#host.services.pageContext.sanitizer;
        const revokeLabel = i18n.t('settings.mcp.tokens.actions.revoke');
        const revokeLabelAttr = sanitizer.attribute(revokeLabel);
        return `<div class="settings-record-actions api-key-actions"><button type="button" data-action="${MCP_ACTION_ACCESS_TOKEN_REVOKE}" class="ui-button ui-button--sm ui-variant-danger" data-token-id="${sanitizer.attribute(token.tokenId)}" aria-label="${revokeLabelAttr}" data-tooltip="${revokeLabelAttr}">${revokeLabel}</button></div>`;
    }

    #renderTokenList(): string {
        return renderSettingsRecordList({
            items: this.#tokens.map((token) => this.#renderTokenItem(token)),
            empty: renderEmptyState({ title: i18n.t('settings.mcp.tokens.list.empty'), className: 'ui-empty-state--simple' }).html,
            className: 'mcp-tokens-list'
        });
    }

    #formatTimestamp(tsMs: number): string {
        return formatPositiveEpochMsSecondWithFallback(tsMs, i18n.t('settings.mcp.tokens.list.never'));
    }
}

export { McpAccessTokensManager };
export type { McpAccessTokenRecord };
