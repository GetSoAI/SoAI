/* SoAI - Settings feature controller [frontend/assets/ts/features/settings/apikeys/controller.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ApiKeySecretResponse } from '@core/api/contracts/apiKeyContracts.ts';
import type { ApiKeyOperation, ApiKeysManagerHost } from '@features/settings/apikeys/types.ts';
import { showApiKeyCreateExpiryModal, showApiKeyCreateLabelModal, showApiKeySecretModal } from '@features/settings/tokenflow/definitions.ts';

const requireSecretValue = (response: ApiKeySecretResponse): string => response.key;

const createApiKeyFlow = async (host: ApiKeysManagerHost, onReload: () => Promise<void>): Promise<void> => {
    return host.execution.runWithBoundary('settings:showCreateApiKeyModal', async (): Promise<void> => {
        let normalizedLabel = '';
        const initialLabel = await showApiKeyCreateLabelModal(normalizedLabel);
        if (initialLabel === null) {
            return;
        }
        normalizedLabel = initialLabel;
        let expiryChoice = await showApiKeyCreateExpiryModal();
        while (expiryChoice === 'back') {
            const nextLabel = await showApiKeyCreateLabelModal(normalizedLabel);
            if (nextLabel === null) {
                return;
            }
            normalizedLabel = nextLabel;
            expiryChoice = await showApiKeyCreateExpiryModal();
        }
        if (expiryChoice === null) {
            return;
        }
        await host.execution.confirmAndExecute(
            'settings:createApiKey',
            null,
            async () => {
                const response = await host.api.createApiKey({
                    scopes: ['OPENAI_API'],
                    ...(normalizedLabel ? { label: normalizedLabel } : {}),
                    ...(expiryChoice === '90days' ? { expiresInDays: 90 } : {})
                });
                const keyValue = requireSecretValue(response);
                await showApiKeySecretModal(keyValue);
                await onReload();
                return null;
            },
            i18n.t('settings.apiKeys.notifications.createSuccess'),
            null,
            null
        );
    });
};

const runApiKeyAction = async (host: ApiKeysManagerHost, action: ApiKeyOperation, keyId: string, onReload: () => Promise<void>): Promise<void> => {
    const config = (() => {
        switch (action) {
            case 'revoke':
                return {
                    boundaryName: 'settings:revokeApiKey',
                    confirmOptions: {
                        title: i18n.t('settings.apiKeys.confirmRevoke.title'),
                        message: i18n.t('settings.apiKeys.confirmRevoke.message'),
                        confirmText: i18n.t('settings.apiKeys.actions.revoke'),
                        cancelText: i18n.t('common.cancel'),
                        variant: 'warning'
                    },
                    apiCall: async (): Promise<void> => {
                        await host.api.revokeApiKey(keyId);
                    },
                    successMessage: i18n.t('settings.apiKeys.notifications.revokeSuccess')
                };
            case 'rotate':
                return {
                    boundaryName: 'settings:rotateApiKey',
                    confirmOptions: {
                        title: i18n.t('settings.apiKeys.confirmRotate.title'),
                        message: i18n.t('settings.apiKeys.confirmRotate.message'),
                        confirmText: i18n.t('settings.apiKeys.actions.rotate'),
                        cancelText: i18n.t('common.cancel'),
                        variant: 'warning'
                    },
                    apiCall: async () => {
                        const result = await host.api.rotateApiKey(keyId);
                        const keyValue = requireSecretValue(result);
                        await showApiKeySecretModal(keyValue);
                        return;
                    },
                    successMessage: i18n.t('settings.apiKeys.notifications.rotateSuccess')
                };
            case 'delete':
                return {
                    boundaryName: 'settings:deleteApiKey',
                    confirmOptions: {
                        title: i18n.t('settings.apiKeys.confirmDelete.title'),
                        message: i18n.t('settings.apiKeys.confirmDelete.message'),
                        confirmText: i18n.t('settings.apiKeys.actions.delete'),
                        cancelText: i18n.t('common.cancel'),
                        variant: 'danger'
                    },
                    apiCall: async (): Promise<void> => {
                        await host.api.deleteApiKey(keyId);
                    },
                    successMessage: i18n.t('settings.apiKeys.notifications.deleteSuccess')
                };
            default: {
                const exhaustive: never = action;
                throw new Error(`Unhandled API key action: ${exhaustive}`);
            }
        }
    })();
    await host.execution.confirmAndExecute(config.boundaryName, config.confirmOptions, config.apiCall, config.successMessage, () => onReload(), null);
};

export { createApiKeyFlow, runApiKeyAction };
