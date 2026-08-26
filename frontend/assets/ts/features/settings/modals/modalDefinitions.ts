/* SoAI - Settings modal definitions registered by app bootstrap [frontend/assets/ts/features/settings/modals/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { settingsApiKeyQuotaModalDefinition } from '@features/settings/apikeys/quotaModal.ts';
import { externalAccountModalDefinition } from '@features/settings/externalaccounts/externalAccountModal.ts';
import { messagingAccountModalDefinition, messagingParametersModalDefinition } from '@features/settings/messaging/modal.ts';
import { mcpServerModalDefinition } from '@features/settings/mcp/mcpServerModal.ts';
import { apiKeyCreateExpiryModalDefinition, apiKeyCreateLabelModalDefinition, apiKeySecretModalDefinition, mcpAccessTokenCreateExpiryModalDefinition, mcpAccessTokenCreateLabelModalDefinition, mcpAccessTokenSecretModalDefinition } from '@features/settings/tokenflow/definitions.ts';

const SETTINGS_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([apiKeyCreateLabelModalDefinition, apiKeyCreateExpiryModalDefinition, apiKeySecretModalDefinition, settingsApiKeyQuotaModalDefinition, mcpAccessTokenCreateLabelModalDefinition, mcpAccessTokenCreateExpiryModalDefinition, mcpAccessTokenSecretModalDefinition, mcpServerModalDefinition, externalAccountModalDefinition, messagingAccountModalDefinition, messagingParametersModalDefinition]);

export { SETTINGS_MODAL_DEFINITIONS };
