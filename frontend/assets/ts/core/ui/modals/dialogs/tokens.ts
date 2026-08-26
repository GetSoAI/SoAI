/* SoAI - Dialogs UI token contract shared between markup and flows [frontend/assets/ts/core/ui/modals/dialogs/tokens.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ConfirmationUiTokens = Readonly<{
    TITLE: 'title';
    ICON: 'icon';
    MESSAGE: 'message';
    DESCRIPTION: 'description';
    CANCEL: 'cancel';
    ACTION_1: 'action-1';
    ACTION_2: 'action-2';
}>;

const CONFIRMATION_UI_TOKENS: ConfirmationUiTokens = Object.freeze({
    TITLE: 'title',
    ICON: 'icon',
    MESSAGE: 'message',
    DESCRIPTION: 'description',
    CANCEL: 'cancel',
    ACTION_1: 'action-1',
    ACTION_2: 'action-2'
});

type PromptUiTokens = Readonly<{
    TITLE: 'title';
    MESSAGE: 'message';
    INPUT: 'input';
    CANCEL: 'cancel';
    CONFIRM: 'confirm';
}>;

const PROMPT_UI_TOKENS: PromptUiTokens = Object.freeze({
    TITLE: 'title',
    MESSAGE: 'message',
    INPUT: 'input',
    CANCEL: 'cancel',
    CONFIRM: 'confirm'
});

type PasswordChangeUiTokens = Readonly<{
    TITLE: 'title';
    DESCRIPTION: 'description';
    CURRENT_LABEL: 'current-label';
    CURRENT: 'current';
    NEW_LABEL: 'new-label';
    NEW: 'new';
    CONFIRM_NEW_LABEL: 'confirm-new-label';
    CONFIRM_NEW: 'confirm-new';
    ERROR: 'error';
    CANCEL: 'cancel';
    SUBMIT: 'submit';
}>;

const PASSWORD_CHANGE_UI_TOKENS: PasswordChangeUiTokens = Object.freeze({
    TITLE: 'title',
    DESCRIPTION: 'description',
    CURRENT_LABEL: 'current-label',
    CURRENT: 'current',
    NEW_LABEL: 'new-label',
    NEW: 'new',
    CONFIRM_NEW_LABEL: 'confirm-new-label',
    CONFIRM_NEW: 'confirm-new',
    ERROR: 'error',
    CANCEL: 'cancel',
    SUBMIT: 'submit'
});

const USERNAME_RENAME_UI_TOKENS = Object.freeze({
    TITLE: 'title',
    DESCRIPTION: 'description',
    USERNAME_LABEL: 'username-label',
    USERNAME: 'username',
    PASSWORD_LABEL: 'password-label',
    PASSWORD: 'password',
    ERROR: 'error',
    CANCEL: 'cancel',
    SUBMIT: 'submit'
});

export { CONFIRMATION_UI_TOKENS, PASSWORD_CHANGE_UI_TOKENS, PROMPT_UI_TOKENS, USERNAME_RENAME_UI_TOKENS };
export type { ConfirmationUiTokens, PasswordChangeUiTokens, PromptUiTokens };
