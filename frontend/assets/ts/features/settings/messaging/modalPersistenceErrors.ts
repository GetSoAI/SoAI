/* SoAI - Messaging account modal persistence error presentation [frontend/assets/ts/features/settings/messaging/modalPersistenceErrors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { extractErrorCode, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';

const resolveMessagingPersistenceError = (error: Error, platform: string): string => {
    if (isErrorHttpStatus(error, 409)) {
        if (extractErrorCode(error) === 'messaging_callback_conflict') return i18n.t('settings.messaging.modal.callbackConflict');
        return i18n.t('settings.messaging.modal.accountConflict');
    }
    if (isErrorHttpStatus(error, 400) || isErrorHttpStatus(error, 422)) {
        if (platform === 'discord') {
            const errorCode = extractErrorCode(error);
            if (errorCode === 'messaging_discord_bot_token_rejected' || errorCode === 'messaging_discord_not_bot') return i18n.t('settings.messaging.modal.discordBotTokenRejected');
            if (errorCode === 'messaging_discord_application_rejected') return i18n.t('settings.messaging.modal.discordApplicationRejected');
            if (errorCode === 'messaging_discord_application_mismatch') return i18n.t('settings.messaging.modal.discordApplicationMismatch');
            if (errorCode === 'messaging_discord_message_content_required') return i18n.t('settings.messaging.modal.discordMessageContentRequired');
            return i18n.t('settings.messaging.modal.discordValidationFailed');
        }
        if (platform === 'whatsapp') {
            const errorCode = extractErrorCode(error);
            if (errorCode === 'messaging_whatsapp_application_credentials_rejected') return i18n.t('settings.messaging.modal.whatsappApplicationCredentialsRejected');
            if (errorCode === 'messaging_whatsapp_access_token_rejected') return i18n.t('settings.messaging.modal.whatsappAccessTokenRejected');
            if (errorCode === 'messaging_whatsapp_application_mismatch') return i18n.t('settings.messaging.modal.whatsappApplicationMismatch');
            if (errorCode === 'messaging_whatsapp_permissions_required') return i18n.t('settings.messaging.modal.whatsappPermissionsRequired');
            return i18n.t('settings.messaging.modal.whatsappValidationFailed');
        }
        return i18n.t('settings.messaging.modal.telegramValidationFailed');
    }
    return i18n.t('settings.messaging.modal.retryableFailure');
};

export { resolveMessagingPersistenceError };
