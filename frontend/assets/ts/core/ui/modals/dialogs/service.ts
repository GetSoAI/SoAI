/* SoAI - Dialogs service (confirmation/external-link/copy-text/prompt) backed by core.modalPresenter [frontend/assets/ts/core/ui/modals/dialogs/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import { getServiceContainer } from '@core/serviceContainer.ts';
import { hasFunctionProperty, isObject, isString } from '@core/typeGuards.ts';
import { resolveVariantIcon, VARIANT_CLASS_MAP } from '@core/ui/modals/dialogs/constants.ts';
import { createConfirmationFlow, type ConfirmationActionButtons } from '@core/ui/modals/dialogs/confirmationFlow.ts';
import { createCopyTextModal } from '@core/ui/modals/dialogs/copyTextModal.ts';
import { createExternalLinkModal } from '@core/ui/modals/dialogs/externalLinkModal.ts';
import { createLocalFolderOpenModal } from '@core/ui/modals/dialogs/localFolderOpenModal.ts';
import { createPasswordChangeFlow } from '@core/ui/modals/dialogs/passwordChangeFlow.ts';
import { createUsernameRenameFlow } from '@core/ui/modals/dialogs/usernameRenameFlow.ts';
import { createPromptFlow } from '@core/ui/modals/dialogs/promptFlow.ts';
import type { ConfirmationOptions, CopyTextModalOptions, ExternalLinkOptions, LocalFolderOpenOptions, PasswordChangeModalOptions, PromptModalOptions, UsernameRenameModalOptions } from '@core/ui/modals/dialogs/types.ts';
import { CONFIRMATION_MODAL_ID, DIALOGS_SERVICE_ID, PASSWORD_CHANGE_MODAL_ID, PROMPT_MODAL_ID, USERNAME_RENAME_MODAL_ID } from '@core/ui/modals/dialogs/ids.ts';

interface DialogsServiceApi {
    showConfirmation: (options: ConfirmationOptions) => Promise<boolean>;
    showExternalLinkModal: (options?: ExternalLinkOptions | undefined) => Promise<boolean>;
    showChatExternalLinkModal: (options?: ExternalLinkOptions | undefined) => Promise<boolean>;
    showLocalFolderOpenModal: (options: LocalFolderOpenOptions) => Promise<boolean>;
    showCopyTextModal: (options: CopyTextModalOptions) => Promise<boolean>;
    showPrompt: (options: PromptModalOptions) => Promise<string | null>;
    showPasswordChange: (options: PasswordChangeModalOptions) => Promise<boolean>;
    showUsernameRename: (options: UsernameRenameModalOptions) => Promise<boolean>;
}

const isDialogsServiceApi = <T>(value: T): value is T & DialogsServiceApi => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'showConfirmation') && hasFunctionProperty(value, 'showExternalLinkModal') && hasFunctionProperty(value, 'showChatExternalLinkModal') && hasFunctionProperty(value, 'showLocalFolderOpenModal') && hasFunctionProperty(value, 'showCopyTextModal') && hasFunctionProperty(value, 'showPrompt') && hasFunctionProperty(value, 'showPasswordChange') && hasFunctionProperty(value, 'showUsernameRename');
};

const requireDialogsService = (): DialogsServiceApi => {
    const candidate = getServiceContainer().get(DIALOGS_SERVICE_ID);
    if (!isDialogsServiceApi(candidate)) {
        throw new Error(`${DIALOGS_SERVICE_ID} does not match DialogsServiceApi`);
    }
    return candidate;
};

const createDialogsService = (): DialogsServiceApi => {
    const confirmationFlow = createConfirmationFlow({ modalId: CONFIRMATION_MODAL_ID });
    const promptFlow = createPromptFlow({ modalId: PROMPT_MODAL_ID });
    const externalLinkModal = createExternalLinkModal({ confirmationFlow });
    const localFolderOpenModal = createLocalFolderOpenModal({ confirmationFlow });
    const copyTextModal = createCopyTextModal({ confirmationFlow });
    const passwordChangeFlow = createPasswordChangeFlow({ modalId: PASSWORD_CHANGE_MODAL_ID });
    const usernameRenameFlow = createUsernameRenameFlow({ modalId: USERNAME_RENAME_MODAL_ID });

    const showConfirmation = async (options: ConfirmationOptions): Promise<boolean> => {
        const defaults: Required<Pick<ConfirmationOptions, 'title' | 'message' | 'confirmText' | 'cancelText' | 'variant'>> = {
            title: i18n.t('common.confirm'),
            message: '',
            confirmText: i18n.t('common.confirm'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        };

        const config: ConfirmationOptions = { ...defaults, ...(options ?? {}) };

        const variant = toTrimmedLower(config.variant || 'danger');
        const icon = config.icon !== false ? config.icon || resolveVariantIcon(variant) : null;
        const confirmVariant = config.confirmVariant || VARIANT_CLASS_MAP[variant] || 'ui-variant-danger';

        const actions: ConfirmationActionButtons = Object.freeze({
            first: {
                text: config.confirmText || defaults.confirmText,
                variantClassName: confirmVariant,
                disabled: false,
                title: null,
                perform: () => true
            },
            second: null
        });

        return await confirmationFlow.show({
            title: config.title || defaults.title,
            typeTokens: ['confirmation', variant],
            icon,
            message: config.message || defaults.message,
            description: isString(config.description) && config.description ? config.description : null,
            allowMessageHtml: config.messageAllowHTML === true,
            allowDescriptionHtml: config.descriptionAllowHTML === true,
            cancelText: config.cancelText || defaults.cancelText,
            actions
        });
    };

    const showPrompt = async (options: PromptModalOptions): Promise<string | null> => {
        const inputType = options.inputType === 'password' ? 'password' : 'text';
        const autocomplete = options.autocomplete ?? 'off';
        const placeholder = options.placeholder ?? '';
        const defaultValue = options.defaultValue ?? '';
        const cancelText = i18n.t('common.cancel');
        const resolvedConfirmText = options.confirmText ?? i18n.t('common.ok');

        return await promptFlow.show({
            title: options.title,
            message: options.message,
            placeholder,
            inputType,
            autocomplete,
            defaultValue,
            cancelText,
            confirmText: resolvedConfirmText,
            validate: options.validate
        });
    };

    return {
        showConfirmation,
        showExternalLinkModal: externalLinkModal.showExternalLinkModal,
        showChatExternalLinkModal: externalLinkModal.showChatExternalLinkModal,
        showLocalFolderOpenModal: localFolderOpenModal.showLocalFolderOpenModal,
        showCopyTextModal: copyTextModal.showCopyTextModal,
        showPrompt,
        showPasswordChange: passwordChangeFlow.show,
        showUsernameRename: usernameRenameFlow.show
    };
};

export { createDialogsService, requireDialogsService };
export type { DialogsServiceApi };
