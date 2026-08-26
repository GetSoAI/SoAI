/* SoAI - Chat page ask user submit hotkey [frontend/assets/ts/pages/chat/controllers/page/events/askUserSubmitHotkey.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import type { ChatRootEventsHost } from '@pages/chat/controllers/page/events/contracts.ts';
import { isActionElementDisabled } from '@pages/chat/controllers/page/events/dispatch.ts';
import { getAskUserQuestionElements, getAskUserSelectedPredefinedOptionButtons, optionalAskUserPreview, optionalAskUserSubmitButton, optionalAskUserTextInput, type ChatActionId } from '@features/chat/public.ts';

const resolveAskUserPreviewForTarget = (host: ChatRootEventsHost, target: Element): HTMLElement | null => {
    const askUserPreview = optionalAskUserPreview(host.shell.ensureRootElement());
    if (!(askUserPreview instanceof HTMLElement) || !askUserPreview.contains(target)) {
        return null;
    }
    return askUserPreview;
};

const dispatchHotkeyDataAction = (host: ChatRootEventsHost, event: KeyboardEvent, operationId: string, action: ChatActionId, actionElement: HTMLElement | null): boolean => {
    if (!(actionElement instanceof HTMLElement)) {
        return true;
    }
    if (isActionElementDisabled(actionElement)) {
        return true;
    }
    host.shell.runUiTask(operationId, () => host.shell.dispatchDataAction(action, actionElement, event));
    return true;
};

const isAskUserPromptComplete = (preview: HTMLElement): boolean => {
    const questions = getAskUserQuestionElements(preview);
    if (questions.length === 0) {
        return false;
    }
    for (const questionElement of questions) {
        const answerMode = questionElement.getAttribute('data-answer-mode');
        if (answerMode === 'text' || answerMode === 'other') {
            const input = optionalAskUserTextInput(questionElement);
            if (!(input instanceof HTMLInputElement) || !readTrimmedInputValue(input)) {
                return false;
            }
            continue;
        }
        if (answerMode === 'options') {
            const selected = getAskUserSelectedPredefinedOptionButtons(questionElement);
            if (selected.length === 0) {
                return false;
            }
            continue;
        }
        return false;
    }
    return true;
};

const handleAskUserHotkeyAction = (host: ChatRootEventsHost, target: Element, event: KeyboardEvent, options: { operationId: string; action: ChatActionId; requireComplete?: boolean; resolveButton: (preview: HTMLElement) => HTMLElement | null }): boolean => {
    const askUserPreview = resolveAskUserPreviewForTarget(host, target);
    if (!(askUserPreview instanceof HTMLElement)) {
        return false;
    }
    event.preventDefault();
    if (options.requireComplete === true && !isAskUserPromptComplete(askUserPreview)) {
        return true;
    }
    return dispatchHotkeyDataAction(host, event, options.operationId, options.action, options.resolveButton(askUserPreview));
};

const handleAskUserSubmitHotkey = (host: ChatRootEventsHost, target: Element, event: KeyboardEvent): boolean => {
    if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey)) {
        return false;
    }
    return handleAskUserHotkeyAction(host, target, event, {
        operationId: 'chat:askUserSubmitHotkey',
        action: 'chat:ask-user-submit',
        requireComplete: true,
        resolveButton: (preview) => optionalAskUserSubmitButton(preview)
    });
};

export { dispatchHotkeyDataAction, handleAskUserHotkeyAction, handleAskUserSubmitHotkey, resolveAskUserPreviewForTarget };
