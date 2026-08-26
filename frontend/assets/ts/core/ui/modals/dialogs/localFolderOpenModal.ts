/* SoAI - Local folder open modal preset backed by the confirmation modal flow [frontend/assets/ts/core/ui/modals/dialogs/localFolderOpenModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';
import { securityApi } from '@core/security/public.ts';
import { resolveVariantIcon, VARIANT_CLASS_MAP } from '@core/ui/modals/dialogs/constants.ts';
import type { ConfirmationActionButtons, ConfirmationFlowApi } from '@core/ui/modals/dialogs/confirmationFlow.ts';
import type { LocalFolderOpenOptions } from '@core/ui/modals/dialogs/types.ts';

interface LocalFolderOpenModalApi {
    showLocalFolderOpenModal: (options: LocalFolderOpenOptions) => Promise<boolean>;
}

const renderFolderDescription = (path: string, description: string | null): string => {
    const leadingDescription = description ? `<p class="confirmation-description">${securityApi.escapeHtml(description)}</p>` : '';
    return `${leadingDescription}<p class="confirmation-description confirmation-description--link"><span class="confirmation-description-link">${securityApi.escapeHtml(path)}</span></p>`;
};

const createLocalFolderOpenModal = (dependencies: { confirmationFlow: ConfirmationFlowApi }): LocalFolderOpenModalApi => {
    const showLocalFolderOpenModal = async (options: LocalFolderOpenOptions): Promise<boolean> => {
        const path = toTrimmedString(options.path);
        if (!path) {
            throw new Error('Local folder confirmation requires a path');
        }
        const variant = toTrimmedLower(options.variant || 'info');
        const icon = options.icon !== false ? options.icon || 'folder' : null;
        const resolvedIcon = options.icon === false ? null : icon || resolveVariantIcon(variant);
        const confirmVariant = options.confirmVariant || VARIANT_CLASS_MAP[variant] || 'ui-variant-neutral';
        const actions: ConfirmationActionButtons = Object.freeze({
            first: {
                text: options.confirmText || i18n.t('chat.confirmations.localFolderConfirm'),
                variantClassName: confirmVariant,
                disabled: false,
                title: null,
                perform: () => true
            },
            second: null
        });

        return await dependencies.confirmationFlow.show({
            title: options.title || i18n.t('chat.confirmations.localFolder'),
            typeTokens: ['confirmation', 'local-folder', variant],
            icon: resolvedIcon,
            message: options.message || i18n.t('chat.confirmations.localFolderMessage'),
            description: renderFolderDescription(path, toTrimmedString(options.description) || null),
            allowMessageHtml: options.messageAllowHTML === true,
            allowDescriptionHtml: true,
            cancelText: options.cancelText || i18n.t('chat.confirmations.externalLinkCancel'),
            actions
        });
    };

    return {
        showLocalFolderOpenModal
    };
};

export { createLocalFolderOpenModal };
export type { LocalFolderOpenModalApi };
