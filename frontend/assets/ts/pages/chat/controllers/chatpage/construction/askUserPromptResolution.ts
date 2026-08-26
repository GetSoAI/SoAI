/* SoAI - Chat page ask user prompt resolution [frontend/assets/ts/pages/chat/controllers/chatpage/construction/askUserPromptResolution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AskUserAnswerRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { getAskUserQuestionElements, getAskUserSelectedPredefinedOptionButtons, optionalAskUserTextInput, CHAT_SELECTORS, type ChatElicitationSession } from '@features/chat/public.ts';
import { CHAT_VALIDATION_NOTIFICATION_DURATION_MS, normalizeResolutionIds } from '@pages/chat/controllers/chatpage/construction/elicitation/guards.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface AskUserPromptResolutionHost extends PageDomOwnerHost, PageFeedbackOwnerHost {
    elicitation: ChatElicitationSession;
    updateInputState(): void;
}

const resolveQuestionAnswerEntries = (questionElement: HTMLElement): string[] => {
    const answerMode = questionElement.getAttribute('data-answer-mode');
    if (answerMode === 'text' || answerMode === 'other') {
        const inputElement = optionalAskUserTextInput(questionElement);
        const inputValue = inputElement ? readTrimmedInputValue(inputElement) : '';
        return inputValue ? [inputValue] : [];
    }
    if (answerMode === 'options') {
        const selectedOptions = getAskUserSelectedPredefinedOptionButtons(questionElement);
        const answerEntries: string[] = [];
        for (const selectedOption of selectedOptions) {
            const optionLabelRaw = selectedOption.getAttribute('data-option-label');
            const optionLabel = toTrimmedString(optionLabelRaw);
            if (optionLabel) {
                answerEntries.push(optionLabel);
            }
        }
        return answerEntries;
    }
    return [];
};

async function resolveAskUserPromptForConstruction(host: AskUserPromptResolutionHost, conversationId: string, taskId: string, action: 'submit' | 'cancel'): Promise<void> {
    const normalized = normalizeResolutionIds(conversationId, taskId);
    if (!normalized) {
        return;
    }

    const { conversationId: normalizedConversationId, taskId: normalizedTaskId } = normalized;

    const elicitation = host.elicitation;
    const prompt = elicitation.getAskUserPrompt(normalizedConversationId);
    if (!prompt || prompt.taskId !== normalizedTaskId) {
        return;
    }

    if (action === 'cancel') {
        await elicitation.resolveAskUser(normalizedConversationId, normalizedTaskId, { action: 'cancel' });
        host.updateInputState();
        return;
    }

    const preview = host.pageDom.optional(CHAT_SELECTORS.ASK_USER_PREVIEW);
    if (!(preview instanceof HTMLElement)) {
        return;
    }

    const answers: Record<string, AskUserAnswerRequest> = {};
    let hasMissingAnswers = false;

    const questionElements = getAskUserQuestionElements(preview);
    for (const questionElement of questionElements) {
        const questionIdRaw = questionElement.getAttribute('data-question-id');
        const questionId = toTrimmedString(questionIdRaw);
        if (!questionId) {
            continue;
        }

        const answerEntries = resolveQuestionAnswerEntries(questionElement);

        if (answerEntries.length === 0) {
            hasMissingAnswers = true;
            continue;
        }

        answers[questionId] = { answers: answerEntries };
    }

    if (hasMissingAnswers || Object.keys(answers).length !== prompt.questions.length) {
        host.feedback.show(i18n.t('chat.askUser.validationRequired'), 'warning', CHAT_VALIDATION_NOTIFICATION_DURATION_MS);
        return;
    }

    await elicitation.resolveAskUser(normalizedConversationId, normalizedTaskId, {
        action: 'submit',
        answers
    });
    host.updateInputState();
}

export { resolveAskUserPromptForConstruction };
