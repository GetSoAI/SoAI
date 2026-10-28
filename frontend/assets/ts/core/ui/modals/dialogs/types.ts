/* SoAI - Shared UI dialogs contracts [frontend/assets/ts/core/ui/modals/dialogs/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConfirmationActionButton, NoticeSection } from '@core/ui/modals/dialogs/confirmationFlow.ts';

interface ClipboardServiceInterface {
    isSupported: () => boolean;
    copyText: (text: string, options?: CopyTextOptions) => Promise<boolean>;
}

interface CopyTextOptions {
    successMessage?: string;
    errorMessage?: string;
    notify?: (message: string, type: string) => void;
}

interface ConfirmationOptions {
    signal?: AbortSignal | undefined;
    title?: string;
    message?: string;
    description?: string;
    confirmText?: string;
    cancelText?: string;
    variant?: string;
    icon?: string | false;
    confirmVariant?: string;
    messageAllowHTML?: boolean;
    descriptionAllowHTML?: boolean;
    advisory?: { text: string; variant: 'info' | 'warning' } | undefined;
    fields?: HTMLElement | undefined;
    onConfirm?: () => Promise<boolean>;
}

interface NoticeOptions {
    sections?: readonly NoticeSection[];
    signal?: AbortSignal | undefined;
    advisory?: { text: string; variant: 'info' | 'warning' };
    action?: ConfirmationActionButton;
    actionErrorText?: string;
    title: string;
    message: string;
    variant: 'success' | 'info' | 'warning' | 'danger';
    description?: string;
    closeText?: string;
}

interface ExternalLinkOptions extends ConfirmationOptions {
    url?: string;
    copyText?: string;
    copySuccessMessage?: string;
    copyErrorMessage?: string;
    copyUnavailableMessage?: string;
}

interface LocalFolderOpenOptions extends ConfirmationOptions {
    path: string;
}

interface CopyTextModalOptions {
    title: string;
    message: string;
    text: string;
    confirmText?: string;
    copyText?: string;
    copyVariant?: string;
    variant?: string;
    icon?: string | false;
    copySuccessMessage?: string;
    copyErrorMessage?: string;
    copyUnavailableMessage?: string;
}

type PromptInputType = 'password' | 'text';

type PromptAutocomplete = 'current-password' | 'new-password' | 'off' | 'on' | 'username';

interface PromptModalOptions {
    title: string;
    message: string;
    defaultValue?: string;
    placeholder?: string;
    inputType?: PromptInputType;
    autocomplete?: PromptAutocomplete;
    confirmText?: string;
    validate?: ((value: string) => string | null) | undefined;
}

interface PasswordChangeValues {
    operationId: string;
    currentPassword: string;
    newPassword: string;
}

interface PasswordChangeFieldLabels {
    current: string;
    new: string;
    confirm: string;
}

interface PasswordChangeValidationMessages {
    currentRequired: string;
    newRequired: string;
    tooLong: string;
    tooShort: string;
    confirmMismatch: string;
    updateFailed: string;
}

interface PasswordChangeModalOptions {
    title: string;
    message: string;
    fieldLabels: PasswordChangeFieldLabels;
    validationMessages: PasswordChangeValidationMessages;
    submitText?: string;
    onSubmit: (values: PasswordChangeValues) => Promise<IdentityMutationModalFailure | null>;
}

interface IdentityMutationModalFailure {
    message: string;
    retainOperationId: boolean;
}

interface UsernameRenameValues {
    operationId: string;
    newUsername: string;
    currentPassword: string;
}

interface UsernameRenameModalOptions {
    title: string;
    message: string;
    usernameLabel: string;
    passwordLabel: string;
    currentUsername: string;
    submitText: string;
    invalidUsername: string;
    unchangedUsername: string;
    passwordRequired: string;
    updateFailed: string;
    onSubmit: (values: UsernameRenameValues) => Promise<IdentityMutationModalFailure | null>;
}

export type { ClipboardServiceInterface, ConfirmationOptions, CopyTextModalOptions, CopyTextOptions, ExternalLinkOptions, IdentityMutationModalFailure, LocalFolderOpenOptions, NoticeOptions, NoticeSection, PasswordChangeFieldLabels, PasswordChangeModalOptions, PasswordChangeValidationMessages, PasswordChangeValues, PromptAutocomplete, PromptInputType, PromptModalOptions, UsernameRenameModalOptions, UsernameRenameValues };
