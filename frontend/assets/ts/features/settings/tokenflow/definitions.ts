/* SoAI - Settings feature definitions [frontend/assets/ts/features/settings/tokenflow/definitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { API_KEYS_CREATE_EXPIRY_MODAL_ID, API_KEYS_CREATE_LABEL_MODAL_ID, API_KEYS_SECRET_MODAL_ID } from '@features/settings/apikeys/constants.ts';
import { SETTINGS_MCP_ACCESS_TOKEN_CREATE_EXPIRY_MODAL_ID, SETTINGS_MCP_ACCESS_TOKEN_CREATE_LABEL_MODAL_ID, SETTINGS_MCP_ACCESS_TOKEN_SECRET_MODAL_ID } from '@features/settings/mcp/constants.ts';
import { createSettingsTokenExpiryModalDefinition, showSettingsTokenExpiryModal } from '@features/settings/tokenflow/expiryModal.ts';
import { createSettingsTokenLabelModalDefinition, showSettingsTokenLabelModal } from '@features/settings/tokenflow/labelModal.ts';
import { createSettingsTokenSecretModalDefinition, showSettingsTokenSecretModal } from '@features/settings/tokenflow/secretModal.ts';
import type { SettingsTokenExpiryChoice, SettingsTokenExpiryModalConfig, SettingsTokenLabelModalConfig, SettingsTokenSecretModalConfig } from '@features/settings/tokenflow/types.ts';

const apiKeyLabelConfig = (): SettingsTokenLabelModalConfig => ({
    modalId: API_KEYS_CREATE_LABEL_MODAL_ID,
    contextLabel: 'Settings API key create label modal',
    text: {
        title: i18n.t('settings.apiKeys.createModal.title'),
        message: i18n.t('settings.apiKeys.createModal.labelField.label'),
        description: i18n.t('settings.apiKeys.createModal.labelField.help')
    },
    placeholder: null,
    required: false
});

const apiKeyExpiryConfig = (): SettingsTokenExpiryModalConfig => ({
    modalId: API_KEYS_CREATE_EXPIRY_MODAL_ID,
    contextLabel: 'Settings API key create expiry modal',
    title: i18n.t('settings.apiKeys.createModal.expiryField.label'),
    help: i18n.t('settings.apiKeys.createModal.expiryField.help'),
    description: i18n.t('settings.apiKeys.createModal.expiryField.description'),
    neverLabel: i18n.t('settings.apiKeys.createModal.expiryField.options.never'),
    ninetyDaysLabel: i18n.t('settings.apiKeys.createModal.expiryField.options.90days')
});

const apiKeySecretConfig = (): SettingsTokenSecretModalConfig => ({
    modalId: API_KEYS_SECRET_MODAL_ID,
    contextLabel: 'Settings API key secret modal',
    title: i18n.t('settings.apiKeys.keyCreated.title'),
    message: i18n.t('settings.apiKeys.keyCreated.message'),
    messageEmphasis: i18n.t('settings.apiKeys.keyCreated.messageEmphasis'),
    copyLabel: i18n.t('settings.apiKeys.keyCreated.copyButton')
});

const mcpAccessTokenLabelConfig = (): SettingsTokenLabelModalConfig => ({
    modalId: SETTINGS_MCP_ACCESS_TOKEN_CREATE_LABEL_MODAL_ID,
    contextLabel: 'Settings MCP access token create label modal',
    text: {
        title: i18n.t('settings.mcp.tokens.create.title'),
        message: i18n.t('settings.mcp.tokens.create.label.label'),
        description: i18n.t('settings.mcp.tokens.create.label.help')
    },
    placeholder: i18n.t('settings.mcp.tokens.create.label.placeholder'),
    required: true
});

const mcpAccessTokenExpiryConfig = (): SettingsTokenExpiryModalConfig => ({
    modalId: SETTINGS_MCP_ACCESS_TOKEN_CREATE_EXPIRY_MODAL_ID,
    contextLabel: 'Settings MCP access token create expiry modal',
    title: i18n.t('settings.mcp.tokens.create.expires.label'),
    help: i18n.t('settings.mcp.tokens.create.expires.help'),
    description: i18n.t('settings.mcp.tokens.create.expires.description'),
    neverLabel: i18n.t('settings.mcp.tokens.create.expires.options.never'),
    ninetyDaysLabel: i18n.t('settings.mcp.tokens.create.expires.options.90days')
});

const mcpAccessTokenSecretConfig = (): SettingsTokenSecretModalConfig => ({
    modalId: SETTINGS_MCP_ACCESS_TOKEN_SECRET_MODAL_ID,
    contextLabel: 'Settings MCP access token secret modal',
    title: i18n.t('settings.mcp.tokens.created.title'),
    message: i18n.t('settings.mcp.tokens.created.message'),
    messageEmphasis: i18n.t('settings.mcp.tokens.created.messageEmphasis'),
    copyLabel: i18n.t('common.copy')
});

const apiKeyCreateLabelModalDefinition = createSettingsTokenLabelModalDefinition(API_KEYS_CREATE_LABEL_MODAL_ID, apiKeyLabelConfig);
const apiKeyCreateExpiryModalDefinition = createSettingsTokenExpiryModalDefinition(API_KEYS_CREATE_EXPIRY_MODAL_ID, apiKeyExpiryConfig);
const apiKeySecretModalDefinition = createSettingsTokenSecretModalDefinition(API_KEYS_SECRET_MODAL_ID, apiKeySecretConfig);

const mcpAccessTokenCreateLabelModalDefinition = createSettingsTokenLabelModalDefinition(SETTINGS_MCP_ACCESS_TOKEN_CREATE_LABEL_MODAL_ID, mcpAccessTokenLabelConfig);
const mcpAccessTokenCreateExpiryModalDefinition = createSettingsTokenExpiryModalDefinition(SETTINGS_MCP_ACCESS_TOKEN_CREATE_EXPIRY_MODAL_ID, mcpAccessTokenExpiryConfig);
const mcpAccessTokenSecretModalDefinition = createSettingsTokenSecretModalDefinition(SETTINGS_MCP_ACCESS_TOKEN_SECRET_MODAL_ID, mcpAccessTokenSecretConfig);

const showApiKeyCreateLabelModal = async (defaultValue: string): Promise<string | null> => await showSettingsTokenLabelModal(apiKeyLabelConfig(), defaultValue);
const showApiKeyCreateExpiryModal = async (): Promise<SettingsTokenExpiryChoice | null> => await showSettingsTokenExpiryModal(apiKeyExpiryConfig());
const showApiKeySecretModal = async (secret: string): Promise<void> => {
    await showSettingsTokenSecretModal(apiKeySecretConfig(), secret);
};

const showMcpAccessTokenCreateLabelModal = async (defaultValue: string): Promise<string | null> => await showSettingsTokenLabelModal(mcpAccessTokenLabelConfig(), defaultValue);
const showMcpAccessTokenCreateExpiryModal = async (): Promise<SettingsTokenExpiryChoice | null> => await showSettingsTokenExpiryModal(mcpAccessTokenExpiryConfig());
const showMcpAccessTokenSecretModal = async (secret: string): Promise<void> => {
    await showSettingsTokenSecretModal(mcpAccessTokenSecretConfig(), secret);
};

export { apiKeyCreateExpiryModalDefinition, apiKeyCreateLabelModalDefinition, apiKeySecretModalDefinition, mcpAccessTokenCreateExpiryModalDefinition, mcpAccessTokenCreateLabelModalDefinition, mcpAccessTokenSecretModalDefinition, showApiKeyCreateExpiryModal, showApiKeyCreateLabelModal, showApiKeySecretModal, showMcpAccessTokenCreateExpiryModal, showMcpAccessTokenCreateLabelModal, showMcpAccessTokenSecretModal };
export type { SettingsTokenExpiryChoice };
