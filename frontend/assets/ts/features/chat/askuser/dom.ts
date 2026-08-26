/* SoAI - Chat feature askuser DOM contracts [frontend/assets/ts/features/chat/askuser/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { optionalRootButton, optionalRootHTMLElement, optionalRootInput, resolveButtonList, resolveHTMLElementList } from '@core/dom/typedElementResolver.ts';
import type { DOMQueryRoot } from '@core/dom/types.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';

const ASK_USER_PREVIEW_SELECTOR = CHAT_SELECTORS.ASK_USER_PREVIEW;
const ASK_USER_QUESTION_SELECTOR = '.ask-user-question';
const ASK_USER_PREDEFINED_OPTION_SELECTOR = '.ask-user-option[data-option-type="predefined"]';
const ASK_USER_SELECTED_PREDEFINED_OPTION_SELECTOR = '.ask-user-option[data-option-type="predefined"][aria-pressed="true"]';
const ASK_USER_OTHER_OPTION_SELECTOR = '.ask-user-option[data-option-type="other"]';
const ASK_USER_TEXT_INPUT_WRAPPER_SELECTOR = '.ask-user-text-input-wrapper';
const ASK_USER_TEXT_INPUT_SELECTOR = '.ask-user-text-input';
const ASK_USER_CANCEL_BUTTON_SELECTOR = '.ask-user-cancel-btn';
const ASK_USER_SUBMIT_BUTTON_SELECTOR = '.ask-user-submit-btn';

const optionalAskUserPreview = (root: DOMQueryRoot): HTMLElement | null => {
    return optionalRootHTMLElement(root, ASK_USER_PREVIEW_SELECTOR, 'Ask user DOM');
};

const optionalAskUserQuestionRootFromChild = (child: HTMLElement): HTMLElement | null => {
    const root = child.closest(ASK_USER_QUESTION_SELECTOR);
    return root instanceof HTMLElement ? root : null;
};

const getAskUserQuestionElements = (preview: HTMLElement): HTMLElement[] => {
    return resolveHTMLElementList(ASK_USER_QUESTION_SELECTOR, preview, 'Ask user DOM question element');
};

const getAskUserPredefinedOptionButtons = (questionRoot: HTMLElement): HTMLButtonElement[] => {
    return resolveButtonList(ASK_USER_PREDEFINED_OPTION_SELECTOR, questionRoot, 'Ask user DOM predefined option');
};

const getAskUserSelectedPredefinedOptionButtons = (questionRoot: HTMLElement): HTMLButtonElement[] => {
    return resolveButtonList(ASK_USER_SELECTED_PREDEFINED_OPTION_SELECTOR, questionRoot, 'Ask user DOM selected option');
};

const optionalAskUserOtherButton = (questionRoot: HTMLElement): HTMLButtonElement | null => {
    return optionalRootButton(questionRoot, ASK_USER_OTHER_OPTION_SELECTOR, 'Ask user DOM');
};

const optionalAskUserTextInputWrapper = (questionRoot: HTMLElement): HTMLElement | null => {
    return optionalRootHTMLElement(questionRoot, ASK_USER_TEXT_INPUT_WRAPPER_SELECTOR, 'Ask user DOM');
};

const optionalAskUserTextInput = (questionRoot: HTMLElement): HTMLInputElement | null => {
    return optionalRootInput(questionRoot, ASK_USER_TEXT_INPUT_SELECTOR, 'Ask user DOM');
};

const optionalAskUserSubmitButton = (preview: HTMLElement): HTMLButtonElement | null => {
    return optionalRootButton(preview, ASK_USER_SUBMIT_BUTTON_SELECTOR, 'Ask user DOM');
};

const optionalAskUserCancelButton = (preview: HTMLElement): HTMLButtonElement | null => {
    return optionalRootButton(preview, ASK_USER_CANCEL_BUTTON_SELECTOR, 'Ask user DOM');
};

const focusAskUserPrompt = (preview: Element | null): void => {
    if (!(preview instanceof HTMLElement)) {
        return;
    }
    const input = dom.resolve(ASK_USER_TEXT_INPUT_SELECTOR, preview);
    if (input instanceof HTMLInputElement && !input.disabled) {
        input.focus({ preventScroll: true });
        return;
    }
    const option = dom.resolve(ASK_USER_PREDEFINED_OPTION_SELECTOR, preview);
    if (option instanceof HTMLButtonElement && !option.disabled) {
        option.focus({ preventScroll: true });
    }
};

export { focusAskUserPrompt, getAskUserPredefinedOptionButtons, getAskUserQuestionElements, getAskUserSelectedPredefinedOptionButtons, optionalAskUserCancelButton, optionalAskUserOtherButton, optionalAskUserPreview, optionalAskUserQuestionRootFromChild, optionalAskUserSubmitButton, optionalAskUserTextInput, optionalAskUserTextInputWrapper };
