/* SoAI - Settings feature MCP search keys [frontend/assets/ts/features/settings/mcp/mcpSearchKeys.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { getSelectDefaultValue, setSelectValueAndSyncDefault } from '@core/dom/selectSelection.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpSearchKeyEntry } from '@core/mcp/contracts.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { renderSettingsRecordList } from '@core/settings/settingsMarkup.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { MCP_SEARCH_PROVIDER_CUSTOM, UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import type { PageSanitizer } from '@features/settings/contracts/contracts.ts';
import { MCP_ACTION_SEARCH_DELETE, MCP_ACTION_SEARCH_EDIT } from '@features/settings/mcp/actions.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import { renderMcpSearchKeyForm } from '@features/settings/mcp/mcpSearchKeyFormView.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';

type McpSearchKeysHost = Pick<McpManagerHost, 'services' | 'view' | 'execution' | 'data'>;

interface McpSearchKeysDependencies {
    host: McpSearchKeysHost;
    reload: () => Promise<boolean>;
}

class McpSearchKeysManager {
    readonly #host: McpSearchKeysHost;
    readonly #reload: () => Promise<boolean>;

    constructor({ host, reload }: McpSearchKeysDependencies) {
        this.#host = host;
        this.#reload = reload;
    }

    hasPendingChanges(): boolean {
        const { select, input } = this.#getSearchProviderFields();
        const apiKeyInput = this.#host.view.pageDom.optional('mcp-search-api-key-input');
        if (!(select instanceof HTMLSelectElement) || !(input instanceof HTMLInputElement)) {
            return false;
        }
        const providerChanged = select.value !== getSelectDefaultValue(select) || input.value !== input.defaultValue;
        const apiKeyChanged = apiKeyInput instanceof HTMLInputElement && apiKeyInput.value !== apiKeyInput.defaultValue;
        return providerChanged || apiKeyChanged;
    }

    isPendingChangesValid(): boolean {
        if (!this.hasPendingChanges()) {
            return true;
        }
        const { select, input } = this.#getSearchProviderFields();
        const apiKeyInput = this.#host.view.pageDom.optional('mcp-search-api-key-input');
        if (!(select instanceof HTMLSelectElement) || !(input instanceof HTMLInputElement) || !(apiKeyInput instanceof HTMLInputElement)) {
            return false;
        }
        const selected = readTrimmedSelectValue(select);
        const isCustom = selected === MCP_SEARCH_PROVIDER_CUSTOM;
        const provider = isCustom ? readTrimmedInputValue(input) : selected;
        const apiKey = readTrimmedInputValue(apiKeyInput);
        return Boolean(provider && apiKey);
    }

    validatePendingChanges(): boolean {
        if (!this.hasPendingChanges()) {
            return true;
        }
        const { select, input } = this.#requireSearchProviderFields();
        const selected = readTrimmedSelectValue(select);
        const isCustom = selected === MCP_SEARCH_PROVIDER_CUSTOM;
        const provider = isCustom ? readTrimmedInputValue(input) : selected;
        const apiKeyInput = this.#requireApiKeyInput();
        const apiKey = readTrimmedInputValue(apiKeyInput);

        if (!provider) {
            this.#host.view.warnAndFocus(isCustom ? input : select, i18n.t('settings.mcp.notifications.searchProviderRequired'));
            return false;
        }
        if (!apiKey) {
            this.#host.view.warnAndFocus(apiKeyInput, i18n.t('settings.mcp.notifications.searchKeyRequired'));
            return false;
        }
        return true;
    }

    syncPendingFieldStates(): void {
        const { select, input } = this.#getSearchProviderFields();
        const apiKeyInput = this.#host.view.pageDom.optional('mcp-search-api-key-input');
        const hasPendingChanges = this.hasPendingChanges();
        if (select instanceof HTMLSelectElement && input instanceof HTMLInputElement) {
            const selected = readTrimmedSelectValue(select);
            const isCustom = selected === MCP_SEARCH_PROVIDER_CUSTOM;
            const provider = isCustom ? readTrimmedInputValue(input) : selected;
            const providerChanged = select.value !== getSelectDefaultValue(select) || input.value !== input.defaultValue;
            this.#host.execution.syncManualDirtyField('mcp.search.provider', providerChanged, !hasPendingChanges || Boolean(provider));
        } else {
            this.#host.execution.clearManualDirtyField('mcp.search.provider');
        }
        if (apiKeyInput instanceof HTMLInputElement) {
            this.#host.execution.syncManualDirtyField('mcp.search.apiKey', apiKeyInput.value !== apiKeyInput.defaultValue, !hasPendingChanges || Boolean(readTrimmedInputValue(apiKeyInput)));
        } else {
            this.#host.execution.clearManualDirtyField('mcp.search.apiKey');
        }
    }

    renderSubgroup(resolveExpanded: McpSectionExpansionResolver): string {
        const mcpData = this.#host.data.getMcpData();
        const form = renderMcpSearchKeyForm(this.#host.services.pageContext.sanitizer, mcpData.searchProviders);

        return renderMcpCollapsibleSection({
            id: 'search',
            title: i18n.t('settings.mcp.searchKeys.title'),
            description: i18n.t('settings.mcp.searchKeys.description'),
            className: 'settings-section--mcp settings-section--mcp-search',
            content: `${form}${renderSettingsRecordList({
                id: UI_IDS.MCP_SEARCH_LIST,
                items: mcpData.searchKeys.map((key) => this.#renderSearchKeyItem(key)),
                empty: renderEmptyState({ title: i18n.t('settings.mcp.searchKeys.empty'), className: 'ui-empty-state--simple' }).html
            })}`,
            resolveExpanded
        });
    }

    async saveSearchKey(options: { reloadAfterSave?: boolean } = {}): Promise<boolean> {
        let shouldReload = false;
        await this.#host.execution.runWithBoundary('settings:saveMcpSearchKey', async () => {
            const { select, input } = this.#requireSearchProviderFields();
            const selected = readTrimmedSelectValue(select);
            const isCustom = selected === MCP_SEARCH_PROVIDER_CUSTOM;
            const provider = isCustom ? readTrimmedInputValue(input) : selected;
            const apiKeyInput = this.#requireApiKeyInput();
            const apiKey = readTrimmedInputValue(apiKeyInput);

            if (!provider) {
                return this.#host.view.warnAndFocus(isCustom ? input : select, i18n.t('settings.mcp.notifications.searchProviderRequired'));
            }
            if (!apiKey) {
                return this.#host.view.warnAndFocus(apiKeyInput, i18n.t('settings.mcp.notifications.searchKeyRequired'));
            }

            await this.#host.services.api.mcp.searchApiKeys.set(provider, { apiKey: apiKey });
            this.#host.execution.feedback.show(i18n.t('settings.mcp.notifications.searchKeySaved'), 'success');

            this.#resetSearchProviderFields();
            shouldReload = true;
            if (options.reloadAfterSave !== false) {
                await this.#reload();
            }
        });
        return shouldReload;
    }

    startSearchKeyEdit(provider: string): void {
        const { select, input } = this.#requireSearchProviderFields();
        const mcpData = this.#host.data.getMcpData();

        if (mcpData.searchProviders.includes(provider)) {
            setSelectValueAndSyncDefault(select, provider);
        } else {
            setSelectValueAndSyncDefault(select, MCP_SEARCH_PROVIDER_CUSTOM);
            input.value = provider;
        }
        this.syncSearchProviderFields(select);

        const apiKeyInput = this.#requireApiKeyInput();
        apiKeyInput.value = '';
        apiKeyInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        apiKeyInput.focus();
    }

    async deleteSearchKey(provider: string): Promise<void> {
        await this.#host.execution.confirmAndExecute(
            'settings:deleteMcpSearchKey',
            {
                title: i18n.t('settings.mcp.confirmDeleteSearchKey.title'),
                message: i18n.t('settings.mcp.confirmDeleteSearchKey.message', { provider }),
                confirmText: i18n.t('settings.mcp.searchKeys.actions.delete'),
                cancelText: i18n.t('common.cancel'),
                variant: 'danger'
            },
            () => this.#host.services.api.mcp.searchApiKeys.delete(provider),
            i18n.t('settings.mcp.notifications.searchKeyDeleted'),
            async () => {
                await this.#reload();
            },
            null
        );
    }

    syncSearchProviderFields(select: HTMLSelectElement): void {
        const fields = this.#requireSearchProviderFields();
        const resolvedSelect = select;
        const resolvedInput = fields.input;

        const selected = readTrimmedSelectValue(resolvedSelect);
        const isCustom = selected === MCP_SEARCH_PROVIDER_CUSTOM;

        if (!isCustom) {
            resolvedInput.value = selected;
        }
        this.#host.view.pageDom.toggleClass(resolvedInput, 'u-hidden', !isCustom);
        setControlDisabledState(resolvedInput, !isCustom);
        this.syncPendingFieldStates();
    }

    #getSearchProviderFields(): { select: Element | null; input: Element | null } {
        return {
            select: this.#host.view.pageDom.optional(UI_IDS.MCP_SEARCH_PROVIDER_SELECT),
            input: this.#host.view.pageDom.optional('mcp-search-provider-input')
        };
    }

    #requireSearchProviderFields(): { select: HTMLSelectElement; input: HTMLInputElement } {
        const { select, input } = this.#getSearchProviderFields();
        if (!(select instanceof HTMLSelectElement)) {
            throw new TypeError('MCP search key provider select missing or invalid');
        }
        if (!(input instanceof HTMLInputElement)) {
            throw new TypeError('MCP search key provider input missing or invalid');
        }
        return { select, input };
    }

    #requireApiKeyInput(): HTMLInputElement {
        const apiKeyInput = this.#host.view.pageDom.require('mcp-search-api-key-input');
        if (!(apiKeyInput instanceof HTMLInputElement)) {
            throw new TypeError('MCP search API key input missing or invalid');
        }
        return apiKeyInput;
    }

    #resetSearchProviderFields(): void {
        const { select, input } = this.#requireSearchProviderFields();
        setSelectValueAndSyncDefault(select, '');
        input.value = '';
        this.syncSearchProviderFields(select);
    }

    #renderSearchKeyItem(key: McpSearchKeyEntry): string {
        const sanitizer = this.#host.services.pageContext.sanitizer;
        const info = this.#buildSearchKeyInfo(key, sanitizer);
        const actions = this.#buildSearchKeyActions(key, sanitizer);
        return `<div class="settings-record-item" data-provider="${sanitizer.attribute(key.provider)}">${info}${actions}</div>`;
    }

    #buildSearchKeyInfo(key: McpSearchKeyEntry, sanitizer: PageSanitizer): string {
        const masked = key.apiKeyMasked ? sanitizer.html(key.apiKeyMasked) : sanitizer.html(i18n.t('settings.mcp.searchKeys.maskedPlaceholder'));
        const sourceMarkup = key.source ? `<span class="mcp-search-source">(${sanitizer.html(key.source)})</span>` : '';
        return `<div class="settings-record-info mcp-search-info"><span class="settings-record-label mcp-search-provider">${sanitizer.html(key.provider)}</span><span class="settings-record-meta mcp-search-masked">${masked}</span>${sourceMarkup}</div>`;
    }

    #buildSearchKeyActions(key: McpSearchKeyEntry, sanitizer: PageSanitizer): string {
        if (key.source === 'env') {
            const badge = sanitizer.html(i18n.t('settings.mcp.searchKeys.source.env'));
            return `<div class="settings-record-actions mcp-search-actions"><span class="settings-record-badge settings-record-badge--neutral mcp-search-source">${badge}</span></div>`;
        }

        if (!key.apiKeyMasked) {
            return '<div class="settings-record-actions mcp-search-actions"></div>';
        }

        const provider = sanitizer.attribute(key.provider);
        const editLabel = i18n.t('settings.mcp.searchKeys.actions.edit');
        const deleteLabel = i18n.t('settings.mcp.searchKeys.actions.delete');
        const editButton = `<button type="button" data-action="${MCP_ACTION_SEARCH_EDIT}" class="ui-button ui-button--sm mcp-search-key-edit-btn" data-provider="${provider}" ${renderLabelAttributes(editLabel)}>${editLabel}</button>`;
        const deleteButton = `<button type="button" data-action="${MCP_ACTION_SEARCH_DELETE}" class="ui-button ui-button--sm ui-variant-danger mcp-search-key-delete-btn" data-provider="${provider}" ${renderLabelAttributes(deleteLabel)}>${deleteLabel}</button>`;
        return `<div class="settings-record-actions mcp-search-actions">${editButton}${deleteButton}</div>`;
    }
}

export { McpSearchKeysManager };
