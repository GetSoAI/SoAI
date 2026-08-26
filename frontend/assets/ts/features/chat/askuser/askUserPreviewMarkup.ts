/* SoAI - Chat feature ask user preview markup [frontend/assets/ts/features/chat/askuser/askUserPreviewMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { renderLabelAttributes, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { AskUserPrompt } from '@features/chat/askuser/askUserModels.ts';
import type { MarkupEscaper } from '@features/chat/message/markupEscaper.ts';

type AskUserPreviewMarkupDependencies = {
    messageManager: MarkupEscaper;
};

function buildAskUserPreviewMarkup(dependencies: AskUserPreviewMarkupDependencies, prompt: AskUserPrompt): TrustedHtml {
    const title = dependencies.messageManager.escapeHtml(i18n.t('chat.askUser.defaultTitle'));
    const taskIdAttr = dependencies.messageManager.escapeAttribute(prompt.taskId);
    const submitLabelText = i18n.t('chat.askUser.submit');
    const cancelLabelText = i18n.t('chat.askUser.cancel');
    const submitLabel = dependencies.messageManager.escapeHtml(submitLabelText);
    const cancelLabel = dependencies.messageManager.escapeHtml(cancelLabelText);
    const textPlaceholder = dependencies.messageManager.escapeAttribute(i18n.t('chat.askUser.textPlaceholder'));
    const otherLabelText = i18n.t('chat.askUser.other');
    const otherLabel = dependencies.messageManager.escapeHtml(otherLabelText);
    const otherDescription = dependencies.messageManager.escapeHtml(i18n.t('chat.askUser.otherDescription'));
    const otherPlaceholder = dependencies.messageManager.escapeAttribute(i18n.t('chat.askUser.otherPlaceholder'));
    const multiSelectHint = dependencies.messageManager.escapeHtml(i18n.t('chat.askUser.multiSelectHint'));

    const header = `<div class="ask-user-header"><div class="ask-user-title">${title}</div></div>`;

    const questions = prompt.questions
        .map((question, index) => {
            const questionIdAttr = dependencies.messageManager.escapeAttribute(question.id);
            const questionHtml = dependencies.messageManager.escapeHtml(question.question);
            const questionIndex = dependencies.messageManager.escapeHtml(i18n.t('chat.askUser.questionLabel', { index: String(index + 1) }));
            const questionHeader = question.header ? `<div class="ask-user-question-header">${dependencies.messageManager.escapeHtml(question.header)}</div>` : '';
            const multiSelectAttr = question.multiSelect ? 'true' : 'false';
            const textInputClassName = `ask-user-text-input form-input${question.isSecret ? ' secret-input' : ''}`;
            const hasOptions = question.options.length > 0;
            const answerModeAttr = hasOptions ? 'options' : 'text';
            const multiSelectHintMarkup = question.multiSelect && hasOptions ? `<div class="ask-user-multi-select-hint">${multiSelectHint}</div>` : '';
            const questionPromptMarkup = `<div class="ask-user-prompt"><span class="ui-status-badge neutral ask-user-question-badge">${questionIndex}</span><span class="ask-user-prompt-text">${questionHtml}</span></div>`;
            const optionsMarkup = hasOptions
                ? question.options
                      .map((option, optionIndex) => {
                          const optionLabelAttr = dependencies.messageManager.escapeAttribute(option.label);
                          const optionLabel = dependencies.messageManager.escapeHtml(option.label);
                          const optionDesc = dependencies.messageManager.escapeHtml(option.description);
                          const buttonIdAttr = dependencies.messageManager.escapeAttribute(`ask_user_${prompt.taskId}_${question.id}_${String(optionIndex)}`);
                          return `<button type="button" class="ask-user-option" id="${buttonIdAttr}" data-action="chat:ask-user-select-option" data-question-id="${questionIdAttr}" data-option-type="predefined" data-option-label="${optionLabelAttr}" aria-pressed="false" ${renderLabelAttributes(option.label)}><span class="ask-user-option-label">${optionLabel}</span><span class="ask-user-option-description">${optionDesc}</span></button>`;
                      })
                      .join('') + `<button type="button" class="ask-user-option ask-user-option--other" data-action="chat:ask-user-select-option" data-question-id="${questionIdAttr}" data-option-type="other" aria-pressed="false" ${renderLabelAttributes(otherLabelText)}><span class="ask-user-option-label">${otherLabel}</span><span class="ask-user-option-description">${otherDescription}</span></button>`
                : '';
            const optionsContainer = optionsMarkup ? `<div class="ask-user-options">${optionsMarkup}</div>` : '';
            const textInputPlaceholder = hasOptions ? otherPlaceholder : textPlaceholder;
            const textInputWrapperClassName = hasOptions ? 'ask-user-text-input-wrapper hidden' : 'ask-user-text-input-wrapper';
            const textInputAriaHidden = hasOptions ? 'true' : 'false';
            const secretInputType = question.isSecret ? resolveSecretInputType() : 'text';
            const rawInputId = `ask_user_${prompt.taskId}_${question.id}_text`;
            const inputId = dependencies.messageManager.escapeAttribute(rawInputId);
            const input = `<input id="${inputId}" class="${textInputClassName}" type="${secretInputType}" data-question-id="${questionIdAttr}" placeholder="${textInputPlaceholder}" />`;
            const inputControl = question.isSecret ? renderSecretInputControl({ inputId: rawInputId, inputMarkup: input }) : input;
            const textInput = `<div class="${textInputWrapperClassName}" aria-hidden="${textInputAriaHidden}">${inputControl}</div>`;
            return `<div class="ask-user-question glass-surface-light glass-surface--bordered glass-surface--rounded" data-question-id="${questionIdAttr}" data-multi-select="${multiSelectAttr}" data-answer-mode="${answerModeAttr}">${questionHeader}${questionPromptMarkup}${multiSelectHintMarkup}${optionsContainer}${textInput}</div>`;
        })
        .join('');

    const footer = `<div class="ask-user-footer"><button type="button" class="ask-user-cancel-btn ui-button ui-variant-neutral" data-action="chat:ask-user-cancel" data-task-id="${taskIdAttr}" ${renderLabelAttributes(cancelLabelText)}>${cancelLabel}</button><button type="button" class="ask-user-submit-btn ui-button ui-variant-success" data-action="chat:ask-user-submit" data-task-id="${taskIdAttr}" ${renderLabelAttributes(submitLabelText)}>${submitLabel}</button></div>`;

    return toTrustedUiHtml(`${header}${questions}${footer}`);
}

export { buildAskUserPreviewMarkup };
