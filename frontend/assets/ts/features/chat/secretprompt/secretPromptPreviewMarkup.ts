/* SoAI - Chat feature secret prompt preview markup [frontend/assets/ts/features/chat/secretprompt/secretPromptPreviewMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';

import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import type { SecretPrompt } from '@features/chat/secretprompt/secretPromptModels.ts';
import { i18n } from '@core/i18n/index.ts';
import { CHAT_ACTION_ID_SECRET_PROMPT_CANCEL, CHAT_ACTION_ID_SECRET_PROMPT_SUBMIT } from '@features/chat/chatConstants.ts';
import type { MarkupEscaper } from '@features/chat/message/markupEscaper.ts';

const buildSecretPromptScopeLabel = (prompt: SecretPrompt): string => {
    return prompt.scope.origin;
};

function buildSecretPromptPreviewMarkup(dependencies: { messageManager: MarkupEscaper }, prompt: SecretPrompt): TrustedHtml {
    const title = dependencies.messageManager.escapeHtml(prompt.title);
    const message = dependencies.messageManager.escapeHtml(prompt.message);
    const scopeLabel = dependencies.messageManager.escapeHtml(buildSecretPromptScopeLabel(prompt));
    const allowSave = prompt.allowSaveToVault === true;
    const taskIdAttr = dependencies.messageManager.escapeAttribute(prompt.taskId);
    const fieldsLayoutClassName = prompt.fields.length >= 2 ? 'secret-prompt-fields secret-prompt-fields--two-col' : 'secret-prompt-fields';
    const resolveFieldLabel = (field: SecretPrompt['fields'][number]): string => {
        switch (field.id) {
            case 'username':
                return i18n.t('chat.secretPrompt.fields.username');
            case 'password':
                return i18n.t('chat.secretPrompt.fields.password');
            default: {
                const exhaustive: never = field.id;
                throw new Error(`Vault secret prompt field label mapping missing for "${String(exhaustive)}"`);
            }
        }
    };
    const buildFieldAutocomplete = (fieldId: string, fieldType: SecretPrompt['fields'][number]['type']): string => {
        if (fieldId === 'username') {
            return 'username';
        }
        if (fieldId === 'password' && fieldType === 'password') {
            return 'current-password';
        }
        return 'off';
    };
    const fieldMarkup = prompt.fields
        .map((field) => {
            const fieldLabel = dependencies.messageManager.escapeHtml(resolveFieldLabel(field));
            const fieldId = dependencies.messageManager.escapeAttribute(field.id);
            const fieldType = dependencies.messageManager.escapeAttribute(field.type);
            const autocomplete = dependencies.messageManager.escapeAttribute(buildFieldAutocomplete(field.id, field.type));
            const required = field.optional ? '' : ' required';
            const rawInputId = `secret_prompt_${prompt.taskId}_${field.id}`;
            const inputId = dependencies.messageManager.escapeAttribute(rawInputId);
            const isSecret = field.type === 'password';
            const resolvedType = isSecret ? dependencies.messageManager.escapeAttribute(resolveSecretInputType()) : fieldType;
            const inputClassName = `secret-prompt-input form-input${isSecret ? ' secret-input' : ''}`;
            const input = `<input id="${inputId}" class="${inputClassName}" type="${resolvedType}" autocomplete="${autocomplete}" data-field-id="${fieldId}"${required}>`;
            const control = isSecret ? renderSecretInputControl({ inputId: rawInputId, inputMarkup: input }) : input;
            return `
                <div class="form-group secret-prompt-field-group">
                    <label for="${inputId}">${fieldLabel}</label>
                    ${control}
                </div>
        `;
        })
        .join('');
    const saveLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.secretPrompt.saveToVault'));
    const labelLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.secretPrompt.label'));
    const submitLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.secretPrompt.submit'));
    const cancelLabel = dependencies.messageManager.escapeHtml(i18n.t('chat.secretPrompt.cancel'));
    const saveLabelDefault = dependencies.messageManager.escapeAttribute(prompt.saveLabelDefault ?? '');
    const enabledLabelAttr = dependencies.messageManager.escapeAttribute(i18n.t('common.enabled'));
    const disabledLabelAttr = dependencies.messageManager.escapeAttribute(i18n.t('common.disabled'));
    const disabledLabelText = dependencies.messageManager.escapeHtml(i18n.t('common.disabled'));
    const saveToggleId = dependencies.messageManager.escapeAttribute(`secret_prompt_save_${prompt.taskId}`);
    const rawLabelInputId = `secret_prompt_label_${prompt.taskId}`;
    const labelInputId = dependencies.messageManager.escapeAttribute(rawLabelInputId);

    const html = `
        <div class="secret-prompt-root" data-task-id="${taskIdAttr}">
            <div class="secret-prompt-header">
                <div class="secret-prompt-title" data-tooltip="${title}">${title}</div>
                <div class="secret-prompt-scope" data-tooltip="${scopeLabel}">${scopeLabel}</div>
            </div>
	            <div class="secret-prompt-body">
	                <div class="secret-prompt-message">${message}</div>
	                <div class="${fieldsLayoutClassName}">
${fieldMarkup}
	                </div>
	                ${
                        allowSave
                            ? `<div class="secret-prompt-save">
                            <div class="secret-prompt-save-row">
                                <span class="secret-prompt-save-label">${saveLabel}</span>
                                <label class="toggle-switch toggle-switch--inline secret-prompt-save-toggle">
                                    <input type="checkbox" id="${saveToggleId}" class="secret-prompt-save-checkbox" data-field-id="save_to_vault" data-toggle-label-true="${enabledLabelAttr}" data-toggle-label-false="${disabledLabelAttr}">
                                    <span class="slider" aria-hidden="true"></span>
                                    <span class="toggle-label">${disabledLabelText}</span>
                                </label>
                            </div>
                            <div class="form-group secret-prompt-field-group secret-prompt-label-field u-hidden" aria-hidden="true" data-field-id="label_wrapper">
                                <label for="${labelInputId}">${labelLabel}</label>
                                <input id="${labelInputId}" class="secret-prompt-input form-input" type="text" autocomplete="off" data-field-id="label" value="${saveLabelDefault}">
                            </div>
                        </div>`
                            : ''
                    }
            </div>
            <div class="secret-prompt-footer">
                <button type="button" class="secret-prompt-cancel-btn ui-button ui-variant-neutral" data-action="${CHAT_ACTION_ID_SECRET_PROMPT_CANCEL}" data-task-id="${taskIdAttr}" ${renderLabelAttributes(i18n.t('chat.secretPrompt.cancel'))}>${cancelLabel}</button>
                <button type="button" class="secret-prompt-submit-btn ui-button ui-variant-success" data-action="${CHAT_ACTION_ID_SECRET_PROMPT_SUBMIT}" data-task-id="${taskIdAttr}" ${renderLabelAttributes(i18n.t('chat.secretPrompt.submit'))}>${submitLabel}</button>
            </div>
        </div>
    `;
    return toTrustedUiHtml(html);
}

export { buildSecretPromptPreviewMarkup };
