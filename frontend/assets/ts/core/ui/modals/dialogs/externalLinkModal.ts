/* SoAI - External link modal presets backed by the confirmation modal flow [frontend/assets/ts/core/ui/modals/dialogs/externalLinkModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import { securityApi } from '@core/security/public.ts';
import { resolveVariantIcon, VARIANT_CLASS_MAP } from '@core/ui/modals/dialogs/constants.ts';
import { copyTextToClipboard, resolveClipboardService } from '@core/ui/modals/dialogs/clipboardCopy.ts';
import type { ConfirmationActionButtons, ConfirmationFlowApi } from '@core/ui/modals/dialogs/confirmationFlow.ts';
import type { ExternalLinkOptions } from '@core/ui/modals/dialogs/types.ts';
import { parseNotificationType } from '@core/ui/notifications/notificationTypeParsing.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';

interface ExternalLinkModalApi {
    showExternalLinkModal: (options?: ExternalLinkOptions | undefined) => Promise<boolean>;
    showChatExternalLinkModal: (options?: ExternalLinkOptions | undefined) => Promise<boolean>;
}

const showExternalLinkModalInternal = async (dependencies: { confirmationFlow: ConfirmationFlowApi }, options: ExternalLinkOptions | undefined, defaults: Readonly<{ title: string; message: string; confirmText: string; cancelText: string; copyText: string; variant: string; icon: string; url: string }>, config: { typeTokens: readonly string[]; copyButtonVariant: string; logContext: string }): Promise<boolean> => {
    const resolved: ExternalLinkOptions = { ...defaults, ...(options ?? {}) };
    const sanitizedUrl = securityApi.sanitizeUrl(resolved.url ?? '', {
        allowRelative: false,
        allowDataImage: false,
        allowBlob: false
    });
    if (!sanitizedUrl) {
        errorHandler.error('Dialogs', `${config.logContext} received an invalid url`, { url: resolved.url });
        showNotification(i18n.t('ui.errors.invalidUrl'), 'error', 6000);
        return false;
    }

    const notify = (messageValue: string, type: string): void => {
        void showNotification(messageValue, parseNotificationType(type));
    };
    const unavailableMessage = resolved.copyUnavailableMessage || i18n.t('common.clipboard.copyUnavailable');
    const url = sanitizedUrl;

    const clipboardService = resolveClipboardService();
    const disabled = !clipboardService || clipboardService.isSupported() !== true;
    const variant = toTrimmedLower(resolved.variant || 'info');
    const icon = resolved.icon !== false ? resolved.icon || resolveVariantIcon(variant) : null;
    const description = (resolved.description ? `<p class="confirmation-description">${resolved.description}</p>` : '') + `<p class="confirmation-description confirmation-description--link"><a class="confirmation-description-link" href="${securityApi.escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${securityApi.escapeHtml(url)}</a></p>`;

    const copy = async (): Promise<boolean> => {
        return await copyTextToClipboard(url, {
            notify,
            successMessage: resolved.copySuccessMessage || i18n.t('common.clipboard.copied'),
            errorMessage: resolved.copyErrorMessage || i18n.t('common.clipboard.copyFailed'),
            unavailableMessage
        });
    };

    const actionButtons: ConfirmationActionButtons = Object.freeze({
        first: {
            text: resolved.copyText || defaults.copyText,
            variantClassName: config.copyButtonVariant,
            disabled,
            title: disabled ? unavailableMessage : null,
            perform: disabled ? null : copy
        },
        second: {
            text: resolved.confirmText || defaults.confirmText,
            variantClassName: VARIANT_CLASS_MAP[variant] || 'ui-variant-neutral',
            disabled: false,
            title: null,
            perform: () => true
        }
    });

    return await dependencies.confirmationFlow.show({
        title: resolved.title || defaults.title,
        typeTokens: [...config.typeTokens, variant],
        icon,
        message: resolved.message || defaults.message,
        description,
        allowMessageHtml: resolved.messageAllowHTML === true,
        allowDescriptionHtml: true,
        cancelText: resolved.cancelText || defaults.cancelText,
        actions: actionButtons
    });
};

const createExternalLinkModal = (dependencies: { confirmationFlow: ConfirmationFlowApi }): ExternalLinkModalApi => {
    const showExternalLinkModal = async (options: ExternalLinkOptions = {}): Promise<boolean> => {
        const defaults = Object.freeze({
            title: i18n.t('common.confirm'),
            message: '',
            confirmText: i18n.t('common.confirm'),
            cancelText: i18n.t('common.cancel'),
            copyText: i18n.t('common.copy'),
            variant: 'info',
            icon: 'external-link',
            url: ''
        });
        return await showExternalLinkModalInternal({ confirmationFlow: dependencies.confirmationFlow }, options, defaults, {
            typeTokens: ['confirmation', 'external-link'],
            copyButtonVariant: 'ui-variant-primary',
            logContext: 'showExternalLinkModal'
        });
    };

    const showChatExternalLinkModal = async (options: ExternalLinkOptions = {}): Promise<boolean> => {
        const defaults = Object.freeze({
            title: i18n.t('chat.confirmations.externalLink'),
            message: i18n.t('chat.confirmations.externalLinkMessage'),
            confirmText: i18n.t('chat.confirmations.externalLinkConfirm'),
            cancelText: i18n.t('chat.confirmations.externalLinkCancel'),
            copyText: i18n.t('common.copy'),
            variant: 'info',
            icon: 'external-link',
            url: ''
        });
        return await showExternalLinkModalInternal({ confirmationFlow: dependencies.confirmationFlow }, options, defaults, {
            typeTokens: ['confirmation', 'external-link', 'chat-external-link'],
            copyButtonVariant: 'ui-variant-primary',
            logContext: 'showChatExternalLinkModal'
        });
    };

    return {
        showExternalLinkModal,
        showChatExternalLinkModal
    };
};

export { createExternalLinkModal };
export type { ExternalLinkModalApi };
