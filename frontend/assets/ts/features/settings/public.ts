/* SoAI - Settings feature public surface [frontend/assets/ts/features/settings/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { AdvancedSettingsRenderer, createAdvancedSettingsRenderer } from '@features/settings/service.ts';
export { formatConfigPathLabel } from '@features/settings/actions.ts';
export { getPreferenceStateLabels, resolvePreferenceStateLabel } from '@features/settings/preferenceStateLabels.ts';
export { SettingsSectionLifecycle } from '@features/settings/sectionLifecycle.ts';
export { createSettingsCapabilityAvailability, markSettingsCapabilityFailed, markSettingsCapabilityReady, renderSettingsCapabilityNotice, resolveSettingsCapabilityMessage, settleSettingsCapability } from '@features/settings/capabilityAvailability.ts';
export type { SettingsCapabilityAvailability, SettledSettingsCapability } from '@features/settings/capabilityAvailability.ts';
export type { AnalyzeStructure, TabDefinition } from '@features/settings/types.ts';
export { ApiKeysManager } from '@features/settings/apikeys/ApiKeysManager.ts';
export { ExternalAccountsManager } from '@features/settings/externalaccounts/ExternalAccountsManager.ts';
export { MessagingManager } from '@features/settings/messaging/MessagingManager.ts';
export { SecurityManager } from '@features/settings/security/SecurityManager.ts';
export { showApiKeyQuotaModal } from '@features/settings/apikeys/quotaModal.ts';
export { SETTINGS_MCP_SERVER_MODAL_ID } from '@features/settings/mcp/constants.ts';
export { McpManager } from '@features/settings/mcp/McpManager.ts';
export { composeNormalTabDefinitions, MCP_SEARCH_PROVIDER_CUSTOM, NORMAL_TAB_DEFINITIONS, PAGE_ID, PAGE_MODULE_ID, transformBackupEntry, UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
export type { StorageService } from '@features/settings/contracts/contracts.ts';
