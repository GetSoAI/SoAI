/* SoAI - Messaging provider configuration descriptors [frontend/assets/ts/features/settings/messaging/descriptors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingPlatform } from '@core/api/contracts/messagingAccountContracts.ts';
import type { MessagingProviderDescriptor } from '@features/settings/messaging/types.ts';

const MESSAGING_PROVIDER_DESCRIPTORS: readonly MessagingProviderDescriptor[] = [
    {
        id: 'telegram',
        fields: Object.freeze([
            { key: 'botToken', uiToken: 'bot-token', inputType: 'password', minLength: 1, maxLength: 512, pattern: null, defaultValue: '' },
            { key: 'webhookSecret', uiToken: 'webhook-secret', inputType: 'password', minLength: 16, maxLength: 256, pattern: /^[A-Za-z0-9_-]+$/, defaultValue: '' }
        ])
    },
    {
        id: 'whatsapp',
        fields: Object.freeze([
            { key: 'accessToken', uiToken: 'access-token', inputType: 'password', minLength: 1, maxLength: 2048, pattern: null, defaultValue: '' },
            { key: 'phoneNumberId', uiToken: 'phone-number-id', inputType: 'text', minLength: 1, maxLength: 255, pattern: null, defaultValue: '' },
            { key: 'businessAccountId', uiToken: 'business-account-id', inputType: 'text', minLength: 1, maxLength: 255, pattern: null, defaultValue: '' },
            { key: 'applicationId', uiToken: 'application-id', inputType: 'text', minLength: 1, maxLength: 255, pattern: null, defaultValue: '' },
            { key: 'apiVersion', uiToken: 'api-version', inputType: 'text', minLength: 4, maxLength: 32, pattern: /^v[1-9][0-9]*\.[0-9]+$/, defaultValue: 'v21.0' },
            { key: 'appSecret', uiToken: 'app-secret', inputType: 'password', minLength: 1, maxLength: 512, pattern: null, defaultValue: '' },
            { key: 'verifyToken', uiToken: 'verify-token', inputType: 'password', minLength: 16, maxLength: 256, pattern: null, defaultValue: '' }
        ])
    },
    {
        id: 'discord',
        fields: Object.freeze([
            { key: 'botToken', uiToken: 'bot-token', inputType: 'password', minLength: 1, maxLength: 512, pattern: null, defaultValue: '' },
            { key: 'applicationId', uiToken: 'application-id', inputType: 'text', minLength: 1, maxLength: 255, pattern: null, defaultValue: '' }
        ])
    }
];

const getMessagingProviderDescriptor = (providerId: MessagingPlatform): MessagingProviderDescriptor => {
    const descriptor = MESSAGING_PROVIDER_DESCRIPTORS.find((candidate) => candidate.id === providerId);
    if (!descriptor) {
        throw new Error(`Unknown messaging provider: ${providerId}`);
    }
    return descriptor;
};

export { MESSAGING_PROVIDER_DESCRIPTORS, getMessagingProviderDescriptor };
