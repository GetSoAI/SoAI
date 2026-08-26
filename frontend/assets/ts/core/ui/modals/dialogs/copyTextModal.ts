/* SoAI - Copy-text modal preset backed by the confirmation modal flow [frontend/assets/ts/core/ui/modals/dialogs/copyTextModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import { securityApi } from '@core/security/public.ts';
import { resolveVariantIcon, VARIANT_CLASS_MAP } from '@core/ui/modals/dialogs/constants.ts';
import { copyTextToClipboard, resolveClipboardService } from '@core/ui/modals/dialogs/clipboardCopy.ts';
import type { ConfirmationActionButtons, ConfirmationFlowApi } from '@core/ui/modals/dialogs/confirmationFlow.ts';
import type { CopyTextModalOptions } from '@core/ui/modals/dialogs/types.ts';
import { parseNotificationType } from '@core/ui/notifications/notificationTypeParsing.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';

interface CopyTextModalApi {
    showCopyTextModal: (options: CopyTextModalOptions) => Promise<boolean>;
}

const createCopyTextModal = (dependencies: { confirmationFlow: ConfirmationFlowApi }): CopyTextModalApi => {
    const showCopyTextModal = async (options: CopyTextModalOptions): Promise<boolean> => {
        const config = {
            confirmText: i18n.t('common.close'),
            copyText: i18n.t('common.copy'),
            copyVariant: 'ui-variant-primary',
            variant: 'info',
            icon: 'copy',
            ...options
        };

        const notify = (messageValue: string, type: string): void => {
            void showNotification(messageValue, parseNotificationType(type));
        };

        const unavailableMessage = config.copyUnavailableMessage || i18n.t('common.clipboard.copyUnavailable');
        const clipboardService = resolveClipboardService();
        const disabled = !clipboardService || clipboardService.isSupported() !== true;
        const variant = toTrimmedLower(config.variant || 'info');
        const icon = config.icon !== false ? config.icon || resolveVariantIcon(variant) : null;

        const description = `<div class="settings-token-secret-display form-row-split manual-path-row"><div class="form-col-main"><input type="text" class="form-input settings-token-secret-field" readonly value="${securityApi.escapeAttribute(config.text)}" spellcheck="false" autocapitalize="off" autocomplete="off"></div></div>`;
        const copy = async (): Promise<boolean> => {
            return await copyTextToClipboard(config.text, {
                notify,
                successMessage: config.copySuccessMessage || i18n.t('common.clipboard.copied'),
                errorMessage: config.copyErrorMessage || i18n.t('common.clipboard.copyFailed'),
                unavailableMessage
            });
        };

        const actionButtons: ConfirmationActionButtons = Object.freeze({
            first: {
                text: config.copyText || i18n.t('common.copy'),
                variantClassName: config.copyVariant || 'ui-variant-primary',
                disabled,
                title: disabled ? unavailableMessage : null,
                perform: disabled ? null : copy
            },
            second: {
                text: config.confirmText || i18n.t('common.close'),
                variantClassName: VARIANT_CLASS_MAP[variant] || 'ui-variant-neutral',
                disabled: false,
                title: null,
                perform: () => true
            }
        });

        return await dependencies.confirmationFlow.show({
            title: config.title,
            typeTokens: ['confirmation', 'copy-text', variant],
            icon,
            message: config.message,
            description,
            allowMessageHtml: false,
            allowDescriptionHtml: true,
            cancelText: i18n.t('common.close'),
            actions: actionButtons
        });
    };

    return { showCopyTextModal };
};

export { createCopyTextModal };
export type { CopyTextModalApi };
