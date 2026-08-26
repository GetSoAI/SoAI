/* SoAI - Chat page ask user action handlers [frontend/assets/ts/pages/chat/controllers/actionhandlers/chatAskUserActionHandlers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import { CHAT_ACTIONS, getAskUserPredefinedOptionButtons, optionalAskUserOtherButton, optionalAskUserQuestionRootFromChild, optionalAskUserTextInput, optionalAskUserTextInputWrapper } from '@features/chat/public.ts';
import { createResolvedNamedTaskActionHandler, type TaskActionResolutionHost } from '@pages/chat/controllers/actionhandlers/taskActionResolutionController.ts';
import type { ChatComposerActionPort } from '@pages/chat/controllers/actionhandlers/core/contracts.ts';

type ChatActionHandler = (actionElement: HTMLElement, event: Event) => void;

type ChatAskUserActionId = typeof CHAT_ACTIONS.ASK_USER_SELECT_OPTION | typeof CHAT_ACTIONS.ASK_USER_SUBMIT | typeof CHAT_ACTIONS.ASK_USER_CANCEL;

type ChatAskUserActionHandlersHost = TaskActionResolutionHost & {
    composer: Pick<ChatComposerActionPort, 'resolveAskUser'>;
};

const createAskUserResolutionAction = (host: ChatAskUserActionHandlersHost, operationId: string, action: 'submit' | 'cancel'): ((actionElement: HTMLElement) => void) => {
    return createResolvedNamedTaskActionHandler(host, operationId, `Chat ask-user ${action} action requires data-task-id`, action, async (conversationId, taskId, resolvedAction) => {
        await host.composer.resolveAskUser(conversationId, taskId, resolvedAction);
    });
};

const setOptionSelected = (option: HTMLButtonElement, selected: boolean): void => {
    option.setAttribute('aria-pressed', selected ? 'true' : 'false');
    option.classList.toggle(CSS_CLASSES.SELECTED, selected);
};

const updatePredefinedSelections = (questionRoot: HTMLElement, resolveSelected: (option: HTMLButtonElement) => boolean): void => {
    const predefinedOptions = getAskUserPredefinedOptionButtons(questionRoot);
    for (const predefinedOption of predefinedOptions) {
        setOptionSelected(predefinedOption, resolveSelected(predefinedOption));
    }
};

const setOtherSelection = (questionRoot: HTMLElement, selected: boolean): void => {
    const otherButton = optionalAskUserOtherButton(questionRoot);
    if (otherButton instanceof HTMLButtonElement) {
        setOptionSelected(otherButton, selected);
    }
};

const clearCustomInput = (questionRoot: HTMLElement): void => {
    const input = optionalAskUserTextInput(questionRoot);
    if (input instanceof HTMLInputElement) {
        input.value = '';
    }
};

const setCustomInputVisibility = (questionRoot: HTMLElement, visible: boolean): void => {
    const wrapper = optionalAskUserTextInputWrapper(questionRoot);
    if (!(wrapper instanceof HTMLElement)) {
        return;
    }
    wrapper.classList.toggle(CSS_CLASSES.HIDDEN, !visible);
    wrapper.setAttribute('aria-hidden', visible ? 'false' : 'true');
};

const activateOtherAnswerMode = (questionRoot: HTMLElement): void => {
    updatePredefinedSelections(questionRoot, () => false);
    setOtherSelection(questionRoot, true);
    questionRoot.setAttribute('data-answer-mode', 'other');
    setCustomInputVisibility(questionRoot, true);
    optionalAskUserTextInput(questionRoot)?.focus();
};

const isMultiSelectModifierEvent = (event: Event): boolean => {
    return event instanceof MouseEvent && (event.ctrlKey || event.metaKey);
};

const activatePredefinedAnswerMode = (questionRoot: HTMLElement, selectedOption: HTMLElement, event: Event): void => {
    const multiSelect = questionRoot.getAttribute('data-multi-select') === 'true';
    const useMultiSelectModifier = multiSelect && isMultiSelectModifierEvent(event);
    setOtherSelection(questionRoot, false);
    setCustomInputVisibility(questionRoot, false);
    clearCustomInput(questionRoot);
    updatePredefinedSelections(questionRoot, (predefinedOption) => {
        if (!useMultiSelectModifier) {
            return predefinedOption === selectedOption;
        }
        const isSelectedOption = predefinedOption === selectedOption;
        if (isSelectedOption) {
            return predefinedOption.getAttribute('aria-pressed') !== 'true';
        }
        return predefinedOption.getAttribute('aria-pressed') === 'true';
    });
    questionRoot.setAttribute('data-answer-mode', 'options');
};

const createChatAskUserActionHandlers = (host: ChatAskUserActionHandlersHost): Record<ChatAskUserActionId, ChatActionHandler> => {
    const submitAction = createAskUserResolutionAction(host, 'chat:askUserSubmit', 'submit');
    const cancelAction = createAskUserResolutionAction(host, 'chat:askUserCancel', 'cancel');
    return {
        [CHAT_ACTIONS.ASK_USER_SELECT_OPTION]: (actionElement: HTMLElement, event: Event): void => {
            event.preventDefault();
            event.stopPropagation();
            const questionRoot = optionalAskUserQuestionRootFromChild(actionElement);
            if (!questionRoot) {
                return;
            }
            if (actionElement.getAttribute('data-option-type') === 'other') {
                activateOtherAnswerMode(questionRoot);
                return;
            }
            activatePredefinedAnswerMode(questionRoot, actionElement, event);
        },
        [CHAT_ACTIONS.ASK_USER_SUBMIT]: submitAction,
        [CHAT_ACTIONS.ASK_USER_CANCEL]: cancelAction
    };
};

export { createChatAskUserActionHandlers };
