/* SoAI - MCP search key form view [frontend/assets/ts/features/settings/mcp/mcpSearchKeyFormView.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { createSettingsManualFieldKey } from '@core/settings/settingsFieldKeys.ts';
import { renderSettingItem, renderSettingsGroup } from '@core/settings/settingsMarkup.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { MCP_SEARCH_PROVIDER_CUSTOM, UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import type { PageSanitizer } from '@features/settings/contracts/contracts.ts';
import { MCP_ACTION_SEARCH_PROVIDER_CHANGE } from '@features/settings/mcp/actions.ts';

const renderMcpSearchKeyForm = (sanitizer: PageSanitizer, providers: string[]): string => {
    const apiKeyInputType = resolveSecretInputType();
    const apiKeyPlaceholder = i18n.t('settings.mcp.searchKeys.form.api_key.placeholder');
    const apiKeyInput = `<input type="${apiKeyInputType}" id="mcp-search-api-key-input" class="setting-input setting-input--wide secret-input" placeholder="${sanitizer.attribute(apiKeyPlaceholder)}">`;

    const options = [`<option value="">${i18n.t('settings.mcp.searchKeys.form.provider.selectPlaceholder')}</option>`, ...providers.map((provider) => `<option value="${sanitizer.attribute(provider)}">${sanitizer.html(provider)}</option>`), `<option value="${MCP_SEARCH_PROVIDER_CUSTOM}">${i18n.t('settings.mcp.searchKeys.form.provider.custom')}</option>`].join('');

    const fields = [
        renderSettingItem({
            label: i18n.t('settings.mcp.searchKeys.form.provider.label'),
            help: i18n.t('settings.mcp.searchKeys.form.provider.help'),
            fieldKey: createSettingsManualFieldKey('mcp.search.provider'),
            control: `${renderStandardDropdownSelectControl(`<select id="${UI_IDS.MCP_SEARCH_PROVIDER_SELECT}" data-action="${MCP_ACTION_SEARCH_PROVIDER_CHANGE}" class="setting-input">${options}</select>`)}<input type="text" id="mcp-search-provider-input" class="setting-input u-hidden" placeholder="${sanitizer.attribute(i18n.t('settings.mcp.searchKeys.form.provider.placeholder'))}">`
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.searchKeys.form.api_key.label'),
            help: i18n.t('settings.mcp.searchKeys.form.api_key.help'),
            fieldKey: createSettingsManualFieldKey('mcp.search.apiKey'),
            control: renderSecretInputControl({ inputId: 'mcp-search-api-key-input', inputMarkup: apiKeyInput })
        })
    ];

    return renderSettingsGroup(fields);
};

export { renderMcpSearchKeyForm };
