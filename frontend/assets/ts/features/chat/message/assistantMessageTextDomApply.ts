/* SoAI - Chat feature assistant message text DOM apply [frontend/assets/ts/features/chat/message/assistantMessageTextDomApply.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { parseSingleRootElement } from '@core/dom/parseSingleRootElement.ts';
import type { AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { patchAssistantMessageTextInPlace } from '@features/chat/message/assistantMessageTextPatching.ts';
import type { ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';

const parseAssistantResponseRoot = (messageText: HTMLElement, markup: string): HTMLElement => {
    const created = parseSingleRootElement({
        documentRef: messageText.ownerDocument,
        html: toTrustedUiHtml(markup),
        context: messageText
    });
    if (!(created instanceof HTMLElement) || !created.classList.contains('message-response')) {
        throw new Error('Assistant message text update produced invalid response markup.');
    }
    return created;
};

const createAssistantMessageTextRoot = (messageText: HTMLElement, responseRoot: HTMLElement): HTMLElement => {
    const createdText = messageText.cloneNode(false);
    if (!(createdText instanceof HTMLElement)) {
        throw new Error('Assistant message text update failed to clone message text root.');
    }
    createdText.appendChild(responseRoot);
    return createdText;
};

const applyAssistantMessageTextUpdate = (inputArguments: { preserveActiveStreamingText?: boolean; existingText: HTMLElement; createdText: HTMLElement; suppressInsertAnimations?: boolean; assistantDomState?: AssistantDomStatePreservation | null }): boolean => {
    const patched = patchAssistantMessageTextInPlace({
        existingText: inputArguments.existingText,
        createdText: inputArguments.createdText,
        preserveActiveStreamingText: inputArguments.preserveActiveStreamingText === true,
        suppressInsertAnimations: inputArguments.suppressInsertAnimations === true,
        ...(inputArguments.assistantDomState !== undefined ? { assistantDomState: inputArguments.assistantDomState } : {})
    });
    if (patched !== null) {
        return patched;
    }
    throw new Error('Assistant message reconcile rejected a non-canonical keyed body without mutating the live tree.');
};

const applyAssistantMessageTextMarkup = (messageText: HTMLElement, markup: string, options: ChatMessageInsertAnimationOptions = {}): void => {
    const responseRoot = parseAssistantResponseRoot(messageText, markup);
    const createdText = createAssistantMessageTextRoot(messageText, responseRoot);
    applyAssistantMessageTextUpdate({
        existingText: messageText,
        createdText,
        suppressInsertAnimations: options.suppressInsertAnimations === true
    });
};

export { applyAssistantMessageTextMarkup, applyAssistantMessageTextUpdate };
