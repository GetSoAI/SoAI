/* SoAI - Messaging account translation labels [frontend/assets/ts/features/settings/messaging/labels.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MessagingAccount, MessagingAccountLifecycleState, MessagingPlatform } from '@core/api/contracts/messagingAccountContracts.ts';
import { i18n } from '@core/i18n/index.ts';

const resolveMessagingProviderTitle = (platform: MessagingPlatform): string => {
    if (platform === 'telegram') return i18n.t('settings.messaging.telegram.title');
    if (platform === 'whatsapp') return i18n.t('settings.messaging.whatsapp.title');
    return i18n.t('settings.messaging.discord.title');
};

const resolveMessagingProviderDescription = (platform: MessagingPlatform): string => {
    if (platform === 'telegram') return i18n.t('settings.messaging.telegram.description');
    if (platform === 'whatsapp') return i18n.t('settings.messaging.whatsapp.description');
    return i18n.t('settings.messaging.discord.description');
};

const resolveMessagingCredentialLabel = (platform: MessagingPlatform, key: string): string => {
    if (platform === 'telegram' && key === 'botToken') return i18n.t('settings.messaging.telegram.botToken.label');
    if (platform === 'telegram' && key === 'webhookSecret') return i18n.t('settings.messaging.telegram.secretToken.label');
    if (platform === 'whatsapp' && key === 'accessToken') return i18n.t('settings.messaging.whatsapp.accessToken.label');
    if (platform === 'whatsapp' && key === 'phoneNumberId') return i18n.t('settings.messaging.whatsapp.phoneNumberId.label');
    if (platform === 'whatsapp' && key === 'businessAccountId') return i18n.t('settings.messaging.whatsapp.businessAccountId.label');
    if (platform === 'whatsapp' && key === 'applicationId') return i18n.t('settings.messaging.whatsapp.applicationId.label');
    if (platform === 'whatsapp' && key === 'apiVersion') return i18n.t('settings.messaging.whatsapp.apiVersion.label');
    if (platform === 'whatsapp' && key === 'appSecret') return i18n.t('settings.messaging.whatsapp.appSecret.label');
    if (platform === 'whatsapp' && key === 'verifyToken') return i18n.t('settings.messaging.whatsapp.verifyToken.label');
    if (platform === 'discord' && key === 'botToken') return i18n.t('settings.messaging.discord.token.label');
    if (platform === 'discord' && key === 'applicationId') return i18n.t('settings.messaging.discord.applicationId.label');
    throw new Error(`Unknown Messaging credential field: ${platform}.${key}`);
};

const resolveMessagingCredentialHelp = (platform: MessagingPlatform, key: string): string => {
    if (platform === 'telegram' && key === 'botToken') return i18n.t('settings.messaging.telegram.botToken.help');
    if (platform === 'telegram' && key === 'webhookSecret') return i18n.t('settings.messaging.telegram.secretToken.help');
    if (platform === 'whatsapp' && key === 'accessToken') return i18n.t('settings.messaging.whatsapp.accessToken.help');
    if (platform === 'whatsapp' && key === 'phoneNumberId') return i18n.t('settings.messaging.whatsapp.phoneNumberId.help');
    if (platform === 'whatsapp' && key === 'businessAccountId') return i18n.t('settings.messaging.whatsapp.businessAccountId.help');
    if (platform === 'whatsapp' && key === 'applicationId') return i18n.t('settings.messaging.whatsapp.applicationId.help');
    if (platform === 'whatsapp' && key === 'apiVersion') return i18n.t('settings.messaging.whatsapp.apiVersion.help');
    if (platform === 'whatsapp' && key === 'appSecret') return i18n.t('settings.messaging.whatsapp.appSecret.help');
    if (platform === 'whatsapp' && key === 'verifyToken') return i18n.t('settings.messaging.whatsapp.verifyToken.help');
    if (platform === 'discord' && key === 'botToken') return i18n.t('settings.messaging.discord.token.help');
    if (platform === 'discord' && key === 'applicationId') return i18n.t('settings.messaging.discord.applicationId.help');
    throw new Error(`Unknown Messaging credential field: ${platform}.${key}`);
};

const resolveMessagingStatusLabel = (state: MessagingAccountLifecycleState): string => {
    if (state === 'enabled') return i18n.t('settings.messaging.accounts.status.active');
    if (state === 'disabled') return i18n.t('settings.messaging.accounts.status.disabled');
    if (state === 'deleting') return i18n.t('settings.messaging.accounts.status.deleting');
    return i18n.t('settings.messaging.accounts.status.degraded');
};

const resolveMessagingHealthLabel = (account: MessagingAccount): string => {
    if (account.healthCode === 'discord_listener_starting') return i18n.t('settings.messaging.accounts.health.gatewayStarting');
    if (account.healthCode !== null || account.lifecycleState === 'degraded') return i18n.t('settings.messaging.accounts.health.needsAttention');
    return i18n.t('settings.messaging.accounts.health.healthy');
};

export { resolveMessagingCredentialHelp, resolveMessagingCredentialLabel, resolveMessagingHealthLabel, resolveMessagingProviderDescription, resolveMessagingProviderTitle, resolveMessagingStatusLabel };
