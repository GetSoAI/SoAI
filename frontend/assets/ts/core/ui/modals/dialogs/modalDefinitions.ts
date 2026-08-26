/* SoAI - Dialogs modal definitions registered by app bootstrap [frontend/assets/ts/core/ui/modals/dialogs/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { CONFIRMATION_MODAL_ID, PASSWORD_CHANGE_MODAL_ID, PROMPT_MODAL_ID, USERNAME_RENAME_MODAL_ID } from '@core/ui/modals/dialogs/ids.ts';
import { CONFIRMATION_UI_TOKENS, PASSWORD_CHANGE_UI_TOKENS, PROMPT_UI_TOKENS, USERNAME_RENAME_UI_TOKENS } from '@core/ui/modals/dialogs/tokens.ts';

const confirmationModalDefinition: ModalDefinition = {
    id: CONFIRMATION_MODAL_ID,
    layout: 'md',
    resizable: false,
    allowFullscreen: false,
    initialFocusSelector: modalUiSelector(CONFIRMATION_MODAL_ID, CONFIRMATION_UI_TOKENS.CANCEL),
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = CONFIRMATION_MODAL_ID;
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('common.confirm'),
            closeLabel: i18n.t('common.close')
        });
        const body = renderModalBody(uiHtml`<div class="confirmation-body"><div id="${uiAttr(modalUiId(modalId, CONFIRMATION_UI_TOKENS.ICON))}" class="confirmation-icon u-hidden" aria-hidden="true"></div><div id="${uiAttr(modalUiId(modalId, CONFIRMATION_UI_TOKENS.MESSAGE))}" class="confirmation-message"></div><div id="${uiAttr(modalUiId(modalId, CONFIRMATION_UI_TOKENS.DESCRIPTION))}" class="confirmation-description u-hidden"></div></div>`);
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, CONFIRMATION_UI_TOKENS.CANCEL), text: i18n.t('common.cancel') }),
            right: uiHtml`${renderModalFooterActionButton({ id: modalUiId(modalId, CONFIRMATION_UI_TOKENS.ACTION_1), text: i18n.t('common.confirm'), variant: 'neutral', className: 'u-hidden', ariaHidden: true })}${renderModalFooterActionButton({ id: modalUiId(modalId, CONFIRMATION_UI_TOKENS.ACTION_2), text: i18n.t('common.confirm'), variant: 'primary', className: 'u-hidden', ariaHidden: true })}`
        });
        return createModalElement({
            id: modalId,
            contentClassName: 'confirmation-modal-content',
            header,
            body,
            footer
        });
    }
};

const promptModalDefinition: ModalDefinition = {
    id: PROMPT_MODAL_ID,
    layout: 'md',
    initialFocusSelector: modalUiSelector(PROMPT_MODAL_ID, PROMPT_UI_TOKENS.INPUT),
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = PROMPT_MODAL_ID;
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('common.confirm'),
            closeLabel: i18n.t('common.close')
        });
        const body = renderModalBody(uiHtml`<p class="prompt-message" id="${uiAttr(modalUiId(modalId, PROMPT_UI_TOKENS.MESSAGE))}"></p><div class="form-group"><input type="text" id="${uiAttr(modalUiId(modalId, PROMPT_UI_TOKENS.INPUT))}" class="form-input" spellcheck="false" autocapitalize="off" autocomplete="off"></div>`);
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, PROMPT_UI_TOKENS.CANCEL), text: i18n.t('common.cancel') }),
            right: renderModalFooterActionButton({ id: modalUiId(modalId, PROMPT_UI_TOKENS.CONFIRM), text: i18n.t('common.ok'), variant: 'accent' })
        });
        return createModalElement({
            id: modalId,
            contentClassName: 'prompt-modal-content',
            header,
            body,
            footer
        });
    }
};

const renderPasswordInput = (modalId: string, token: string, autocomplete: string): TrustedHtml => {
    const inputId = modalUiId(modalId, token);
    return toTrustedUiHtml(
        renderSecretInputControl({
            inputId,
            inputMarkup: `<input type="${uiAttr(resolveSecretInputType()).html}" id="${uiAttr(inputId).html}" class="form-input secret-input" spellcheck="false" autocapitalize="off" autocomplete="${uiAttr(autocomplete).html}">`
        })
    );
};

const renderPasswordField = (options: { modalId: string; inputToken: string; labelToken: string; label: string; autocomplete: string }): ReturnType<typeof uiHtml> => {
    const labelId = modalUiId(options.modalId, options.labelToken);
    return uiHtml`<div class="form-group"><label id="${uiAttr(labelId)}" for="${uiAttr(modalUiId(options.modalId, options.inputToken))}">${options.label}</label>${renderPasswordInput(options.modalId, options.inputToken, options.autocomplete)}</div>`;
};

const passwordChangeModalDefinition: ModalDefinition = {
    id: PASSWORD_CHANGE_MODAL_ID,
    layout: 'md',
    initialFocusSelector: modalUiSelector(PASSWORD_CHANGE_MODAL_ID, PASSWORD_CHANGE_UI_TOKENS.CURRENT),
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = PASSWORD_CHANGE_MODAL_ID;
        const header = renderStandardModalHeader({
            modalId,
            title: i18n.t('common.confirm'),
            description: '',
            descriptionId: modalUiId(modalId, PASSWORD_CHANGE_UI_TOKENS.DESCRIPTION),
            closeLabel: i18n.t('common.close')
        });
        const currentField = renderPasswordField({
            modalId,
            inputToken: PASSWORD_CHANGE_UI_TOKENS.CURRENT,
            labelToken: PASSWORD_CHANGE_UI_TOKENS.CURRENT_LABEL,
            label: '',
            autocomplete: 'current-password'
        });
        const newField = renderPasswordField({
            modalId,
            inputToken: PASSWORD_CHANGE_UI_TOKENS.NEW,
            labelToken: PASSWORD_CHANGE_UI_TOKENS.NEW_LABEL,
            label: '',
            autocomplete: 'new-password'
        });
        const confirmField = renderPasswordField({
            modalId,
            inputToken: PASSWORD_CHANGE_UI_TOKENS.CONFIRM_NEW,
            labelToken: PASSWORD_CHANGE_UI_TOKENS.CONFIRM_NEW_LABEL,
            label: '',
            autocomplete: 'new-password'
        });
        const body = renderModalBody(uiHtml`${currentField}${newField}${confirmField}<div class="form-disclaimer form-disclaimer-error" id="${uiAttr(modalUiId(modalId, PASSWORD_CHANGE_UI_TOKENS.ERROR))}" role="alert" aria-live="polite" hidden></div>`);
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, PASSWORD_CHANGE_UI_TOKENS.CANCEL), text: i18n.t('common.cancel') }),
            right: renderModalFooterActionButton({ id: modalUiId(modalId, PASSWORD_CHANGE_UI_TOKENS.SUBMIT), text: i18n.t('common.save'), variant: 'warning' })
        });
        return createModalElement({
            id: modalId,
            contentClassName: 'prompt-modal-content password-change-modal-content',
            header,
            body,
            footer
        });
    }
};

const usernameRenameModalDefinition: ModalDefinition = {
    id: USERNAME_RENAME_MODAL_ID,
    layout: 'md',
    initialFocusSelector: modalUiSelector(USERNAME_RENAME_MODAL_ID, USERNAME_RENAME_UI_TOKENS.USERNAME),
    createElement: (): HTMLElement => {
        const modalId = USERNAME_RENAME_MODAL_ID;
        const header = renderStandardModalHeader({ modalId, title: '', description: '', descriptionId: modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.DESCRIPTION), closeLabel: i18n.t('common.close') });
        const usernameInputId = modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.USERNAME);
        const passwordLabelId = modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.PASSWORD_LABEL);
        const passwordInputId = modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.PASSWORD);
        const passwordInput = renderSecretInputControl({
            inputId: passwordInputId,
            inputMarkup: `<input type="${uiAttr(resolveSecretInputType()).html}" id="${uiAttr(passwordInputId).html}" class="form-input secret-input" spellcheck="false" autocapitalize="off" autocomplete="current-password">`
        });
        const body = renderModalBody(uiHtml`<div class="form-group"><label id="${uiAttr(modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.USERNAME_LABEL))}" for="${uiAttr(usernameInputId)}"></label><input id="${uiAttr(usernameInputId)}" class="form-input" type="text" autocomplete="username" maxlength="50" spellcheck="false" autocapitalize="off"></div><div class="form-group"><label id="${uiAttr(passwordLabelId)}" for="${uiAttr(passwordInputId)}"></label>${toTrustedUiHtml(passwordInput)}</div><div class="form-disclaimer form-disclaimer-error" id="${uiAttr(modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.ERROR))}" role="alert" aria-live="polite" hidden></div>`);
        const footer = renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId, id: modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.CANCEL), text: i18n.t('common.cancel') }),
            right: renderModalFooterActionButton({ id: modalUiId(modalId, USERNAME_RENAME_UI_TOKENS.SUBMIT), text: i18n.t('common.save'), variant: 'neutral' })
        });
        return createModalElement({ id: modalId, contentClassName: 'prompt-modal-content username-rename-modal-content', header, body, footer });
    }
};

const DIALOGS_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([confirmationModalDefinition, promptModalDefinition, passwordChangeModalDefinition, usernameRenameModalDefinition]);

export { DIALOGS_MODAL_DEFINITIONS };
