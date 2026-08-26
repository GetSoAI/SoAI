/* SoAI - Settings feature MCP rendering [frontend/assets/ts/features/settings/mcp/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import type { McpServer } from '@core/mcp/contracts.ts';
import { MCP_SERVER_AUTH_API_KEY, MCP_SERVER_AUTH_NONE, MCP_SERVER_AUTH_OAUTH, MCP_SERVER_TRANSPORT_STDIO, MCP_SERVER_TRANSPORT_STREAMABLE_HTTP } from '@core/mcp/serverValues.ts';
import { toTrustedHtml } from '@core/security/public.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderSettingItem, renderSettingsGroup, renderSettingsSubgroup, renderToggleControl } from '@core/settings/settingsMarkup.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { MCP_SERVER_TIMEOUT_DEFAULT_SECONDS, MCP_SERVER_TIMEOUT_MAX_SECONDS, MCP_SERVER_TIMEOUT_MIN_SECONDS, isMcpServerOauthAuth } from '@features/settings/mcp/mcpServerFormRules.ts';
import { resolveMcpOauthStatusLabel } from '@features/settings/mcp/mcpOauthState.ts';
import { getPreferenceStateLabels, resolvePreferenceStateLabel } from '@features/settings/preferenceStateLabels.ts';

export { getPreferenceStateLabels, resolvePreferenceStateLabel };

export const resolveServerStatusClass = (server: McpServer): string => {
    if (server.status === 'connected') return 'settings-record-badge--active';
    if (server.status === 'auth_required') return 'settings-record-badge--warning';
    if (server.status === 'error') return 'settings-record-badge--danger';
    return 'settings-record-badge--neutral';
};

export const resolveServerStatusLabel = (status: string | null | undefined): string => {
    switch (status) {
        case null:
        case undefined:
            return i18n.t('settings.mcp.servers.status.disconnected');
        case 'connected':
            return i18n.t('settings.mcp.servers.status.connected');
        case 'connecting':
            return i18n.t('settings.mcp.servers.status.connecting');
        case 'reconnecting':
            return i18n.t('settings.mcp.servers.status.reconnecting');
        case 'disconnected':
            return i18n.t('settings.mcp.servers.status.disconnected');
        case 'auth_required':
            return i18n.t('settings.mcp.servers.status.auth_required');
        case 'error':
            return i18n.t('settings.mcp.servers.status.error');
        case 'unknown':
            return i18n.t('settings.mcp.servers.status.unknown');
        default:
            return i18n.t('settings.mcp.servers.status.unknown');
    }
};

export const resolveOauthStatusLabel = (server: McpServer): string | null => {
    if (!isMcpServerOauthAuth(server.authType)) {
        return null;
    }
    return resolveMcpOauthStatusLabel(server.oauthStatus ?? 'none');
};

export const resolveTransportLabel = (transport: string): string => {
    switch (transport) {
        case MCP_SERVER_TRANSPORT_STDIO:
            return i18n.t('settings.mcp.servers.transport.stdio');
        case MCP_SERVER_TRANSPORT_STREAMABLE_HTTP:
            return i18n.t('settings.mcp.servers.transport.streamable_http');
        default:
            return transport;
    }
};

const renderMcpTextInputControl = (modalId: string, inputId: string, placeholder: string): string => {
    return `<input type="text" id="${uiAttr(modalUiId(modalId, inputId)).html}"` + ` class="setting-input setting-input--wide" value=""` + ` placeholder="${uiAttr(placeholder).html}">`;
};

const renderMcpSecretInputControl = (modalId: string, inputId: string, placeholder: string, secretInputType: string): string => {
    const resolvedInputId = modalUiId(modalId, inputId);
    const input = `<input type="${uiAttr(secretInputType).html}" id="${uiAttr(resolvedInputId).html}"` + ` class="setting-input setting-input--wide secret-input" value=""` + ` placeholder="${uiAttr(placeholder).html}">`;
    return renderSecretInputControl({ inputId: resolvedInputId, inputMarkup: input });
};

const renderMcpTextareaControl = (modalId: string, textareaId: string, placeholder: string): string => {
    return `<textarea id="${uiAttr(modalUiId(modalId, textareaId)).html}"` + ` class="setting-textarea setting-textarea--wide" rows="3"` + ` placeholder="${uiAttr(placeholder).html}"></textarea>`;
};

const buildMcpServerModalBodyMarkup = (modalId: string): string => {
    const preferenceLabels = getPreferenceStateLabels();
    const secretInputType = resolveSecretInputType();

    const transportOptions = [
        { value: MCP_SERVER_TRANSPORT_STREAMABLE_HTTP, label: i18n.t('settings.mcp.servers.transport.streamable_http') },
        { value: MCP_SERVER_TRANSPORT_STDIO, label: i18n.t('settings.mcp.servers.transport.stdio') }
    ]
        .map((option) => `<option value="${uiAttr(option.value).html}">${option.label}</option>`)
        .join('');

    const authOptions = [
        { value: MCP_SERVER_AUTH_OAUTH, label: i18n.t('settings.mcp.servers.auth.oauth') },
        { value: MCP_SERVER_AUTH_API_KEY, label: i18n.t('settings.mcp.servers.auth.api_key') },
        { value: MCP_SERVER_AUTH_NONE, label: i18n.t('settings.mcp.servers.auth.none') }
    ]
        .map((option) => `<option value="${uiAttr(option.value).html}">${option.label}</option>`)
        .join('');

    const items = [
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.name.label'),
            help: i18n.t('settings.mcp.servers.form.name.help'),
            control: renderMcpTextInputControl(modalId, 'name-input', i18n.t('settings.mcp.servers.form.name.placeholder'))
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.transport.label'),
            help: i18n.t('settings.mcp.servers.form.transport.help'),
            control: renderStandardDropdownSelectControl(`<select id="${uiAttr(modalUiId(modalId, 'transport-select')).html}" class="setting-input setting-input--wide">${transportOptions}</select>`)
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.auth.label'),
            help: i18n.t('settings.mcp.servers.form.auth.help'),
            control: renderStandardDropdownSelectControl(`<select id="${uiAttr(modalUiId(modalId, 'auth-select')).html}" class="setting-input setting-input--wide">${authOptions}</select>`)
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.endpoint.label'),
            help: i18n.t('settings.mcp.servers.form.endpoint.help'),
            control: renderMcpTextInputControl(modalId, 'endpoint-input', i18n.t('settings.mcp.servers.form.endpoint.placeholder'))
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.timeout.label'),
            help: i18n.t('settings.mcp.servers.form.timeout.help'),
            control: `<input type="number" id="${uiAttr(modalUiId(modalId, 'timeout-input')).html}" class="setting-input"` + ` min="${String(MCP_SERVER_TIMEOUT_MIN_SECONDS)}" max="${String(MCP_SERVER_TIMEOUT_MAX_SECONDS)}" step="1"` + ` value="${String(MCP_SERVER_TIMEOUT_DEFAULT_SECONDS)}">`
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.auto_reconnect.label'),
            help: i18n.t('settings.mcp.servers.form.auto_reconnect.help'),
            control: renderToggleControl({
                id: modalUiId(modalId, 'auto-reconnect-toggle'),
                checked: true,
                labels: preferenceLabels
            })
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.enabled.label'),
            help: i18n.t('settings.mcp.servers.form.enabled.help'),
            className: 'u-hidden',
            attributes: { id: modalUiId(modalId, 'enabled-item') },
            control: renderToggleControl({
                id: modalUiId(modalId, 'enabled-toggle'),
                checked: true,
                labels: preferenceLabels
            })
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.api_key.label'),
            help: i18n.t('settings.mcp.servers.form.api_key.help'),
            className: 'u-hidden',
            attributes: { id: modalUiId(modalId, 'api-key-item') },
            control: renderMcpSecretInputControl(modalId, 'api-key-input', i18n.t('settings.mcp.servers.form.api_key.placeholder'), secretInputType)
        })
    ];

    const manualSection = renderSettingsSubgroup({
        title: i18n.t('settings.mcp.servers.oauthManual.title'),
        attributes: { id: modalUiId(modalId, 'oauth-manual-client'), hidden: true },
        content: renderSettingsGroup([
            renderSettingItem({
                label: i18n.t('settings.mcp.servers.oauthManual.clientId.label'),
                help: i18n.t('settings.mcp.servers.oauthManual.clientId.help'),
                control: renderMcpTextInputControl(modalId, 'oauth-client-id-input', i18n.t('settings.mcp.servers.oauthManual.clientId.placeholder'))
            }),
            renderSettingItem({
                label: i18n.t('settings.mcp.servers.oauthManual.clientSecret.label'),
                help: i18n.t('settings.mcp.servers.oauthManual.clientSecret.help'),
                control: renderMcpSecretInputControl(modalId, 'oauth-client-secret-input', i18n.t('settings.mcp.servers.oauthManual.clientSecret.placeholder'), secretInputType)
            })
        ])
    });

    const advancedItems = [
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.args.label'),
            help: i18n.t('settings.mcp.servers.form.args.help'),
            control: renderMcpTextareaControl(modalId, 'args-input', i18n.t('settings.mcp.servers.form.args.placeholder'))
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.env.label'),
            help: i18n.t('settings.mcp.servers.form.env.help'),
            control: renderMcpTextareaControl(modalId, 'env-input', i18n.t('settings.mcp.servers.form.env.placeholder'))
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.servers.form.headers.label'),
            help: i18n.t('settings.mcp.servers.form.headers.help'),
            control: renderMcpTextareaControl(modalId, 'headers-input', i18n.t('settings.mcp.servers.form.headers.placeholder'))
        })
    ];

    const summaryId = modalUiId(modalId, 'summary');
    return `<div id="${uiAttr(summaryId).html}" class="form-help u-hidden"></div>` + renderSettingsGroup(items) + manualSection + renderSettingsSubgroup({ title: i18n.t('settings.mcp.servers.advancedTitle'), content: renderSettingsGroup(advancedItems) });
};

export const createMcpServerModalElement = (modalId: string): HTMLElement => {
    const header = renderStandardModalHeader({
        modalId,
        title: i18n.t('settings.mcp.servers.addTitle'),
        description: i18n.t('common.modalDescriptions.settingsMcpServer'),
        titleId: modalUiId(modalId, 'title'),
        closeLabel: i18n.t('common.close')
    });
    const body = renderModalBody(toTrustedHtml(buildMcpServerModalBodyMarkup(modalId)));
    const cancelText = i18n.t('common.cancel');
    const saveText = i18n.t('settings.mcp.servers.actions.saveAuthorize');
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: cancelText }),
        right: renderModalFooterActionButton({ id: modalUiId(modalId, 'save-btn'), text: saveText, variant: 'accent' })
    });
    return createModalElement({
        id: modalId,
        labelledBy: modalUiId(modalId, 'title'),
        rootAttributes: { 'data-page-scope': 'settings' },
        header,
        body,
        footer
    });
};
