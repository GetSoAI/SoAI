/* SoAI - Chat feature assistant message text patching [frontend/assets/ts/features/chat/message/assistantMessageTextPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { syncAttributes, syncClass } from '@core/dom/patching.ts';
import type { AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { patchAssistantBodyChildrenInPlace } from '@features/chat/message/assistantBodyKeyedReconciler.ts';
import { patchStreamingTimelineSegmentInPlace } from '@features/chat/message/assistantTimelineSegmentPatching.ts';
import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, buildAssistantBodyItems, resolveAssistantMessageResponseRoot } from '@features/chat/message/assistantMessageMarkupParts.ts';
import type { ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';
import { COLLAPSED_LOADING_CONTENT_DATA_ATTR, COLLAPSED_LOADING_CONTENT_DATA_VALUE, COLLAPSED_LOADING_CONTENT_SELECTOR, COLLAPSED_LOADING_SUMMARY_SELECTOR } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { hasStreamSegments, resolveDirectStreamSegments } from '@features/chat/stream/streamSegmentsMarker.ts';

const hasTerminalSensitiveStreamingBody = (response: HTMLElement): boolean => {
    return hasStreamSegments(response) || dom.resolve(COLLAPSED_LOADING_SUMMARY_SELECTOR, response) !== null || dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, response) !== null;
};

const isCollapsibleLoadingActivity = (element: HTMLElement): boolean => {
    return element.classList.contains('inline-activity') && !element.classList.contains('inline-activity-type-loading');
};

const isExpandedLoadingContentChild = (element: HTMLElement): boolean => {
    return !element.classList.contains('inline-action-update') && !isCollapsibleLoadingActivity(element) && !element.classList.contains('inline-activity-type-loading') && !element.classList.contains('assistant-activity-widgets') && !element.classList.contains('message-error');
};

const prepareCollapsedLoadingContentPatch = (existingResponse: HTMLElement, createdResponse: HTMLElement): void => {
    if (dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, existingResponse) !== null || dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, createdResponse) === null) {
        return;
    }
    const contentChildren = Array.from(existingResponse.children).filter((child): child is HTMLElement => child instanceof HTMLElement && isExpandedLoadingContentChild(child));
    const firstContentChild = contentChildren[0] ?? null;
    if (firstContentChild === null) {
        return;
    }
    const wrapper = existingResponse.ownerDocument.createElement('div');
    wrapper.setAttribute(COLLAPSED_LOADING_CONTENT_DATA_ATTR, COLLAPSED_LOADING_CONTENT_DATA_VALUE);
    const createdWrapper = dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, createdResponse);
    if (!(createdWrapper instanceof HTMLElement)) {
        return;
    }
    const wrapperKey = createdWrapper.getAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME);
    const wrapperSignature = createdWrapper.getAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME);
    if (!wrapperKey || !wrapperSignature) {
        return;
    }
    wrapper.setAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, wrapperKey);
    wrapper.setAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, wrapperSignature);
    existingResponse.insertBefore(wrapper, firstContentChild);
    for (const child of contentChildren) {
        wrapper.appendChild(child);
    }
};

type AssistantTextPatchRoots = {
    existingResponse: HTMLElement;
    createdResponse: HTMLElement;
    existingStreamSegments: HTMLElement | null;
    createdStreamSegments: HTMLElement | null;
    createdCollapsedContent: Element | null;
};

type AssistantTextPatchRoot = {
    response: HTMLElement;
    streamSegments: HTMLElement | null;
};

const resolveAssistantTextPatchRoot = (textRoot: HTMLElement): AssistantTextPatchRoot | null => {
    const response = resolveAssistantMessageResponseRoot(textRoot);
    if (!response) {
        return null;
    }
    const streamSegments = resolveDirectStreamSegments(response);
    if (buildAssistantBodyItems(streamSegments ?? response) === null) {
        return null;
    }
    return { response, streamSegments };
};

const resolveAssistantTextPatchRoots = (existingText: HTMLElement, createdText: HTMLElement): AssistantTextPatchRoots | null => {
    const existing = resolveAssistantTextPatchRoot(existingText);
    const created = resolveAssistantTextPatchRoot(createdText);
    if (!existing || !created) {
        return null;
    }
    return {
        existingResponse: existing.response,
        createdResponse: created.response,
        existingStreamSegments: existing.streamSegments,
        createdStreamSegments: created.streamSegments,
        createdCollapsedContent: dom.resolve(COLLAPSED_LOADING_CONTENT_SELECTOR, created.response)
    };
};

const hasCanonicalAssistantMessageTextBody = (textRoot: HTMLElement): boolean => resolveAssistantTextPatchRoot(textRoot) !== null;

const canPatchAssistantMessageTextInPlace = (existingText: HTMLElement, createdText: HTMLElement): boolean => resolveAssistantTextPatchRoots(existingText, createdText) !== null;

const patchAssistantMessageTextInPlace = (inputArguments: { existingText: HTMLElement; createdText: HTMLElement; suppressInsertAnimations?: ChatMessageInsertAnimationOptions['suppressInsertAnimations']; assistantDomState?: AssistantDomStatePreservation | null }): boolean | null => {
    const roots = resolveAssistantTextPatchRoots(inputArguments.existingText, inputArguments.createdText);
    if (roots === null) {
        return null;
    }
    const { existingResponse, createdResponse, existingStreamSegments, createdStreamSegments, createdCollapsedContent } = roots;
    const terminalSensitiveStreamingBody = hasTerminalSensitiveStreamingBody(existingResponse);
    let changed = false;
    if (syncClass(inputArguments.existingText, inputArguments.createdText)) {
        changed = true;
    }
    if (syncAttributes({ target: inputArguments.existingText, source: inputArguments.createdText })) {
        changed = true;
    }
    if (syncClass(existingResponse, createdResponse)) {
        changed = true;
    }
    if (syncAttributes({ target: existingResponse, source: createdResponse })) {
        changed = true;
    }
    prepareCollapsedLoadingContentPatch(existingResponse, createdResponse);
    if (existingStreamSegments !== null && createdStreamSegments === null && !(createdCollapsedContent instanceof HTMLElement)) {
        existingStreamSegments.replaceWith(...Array.from(existingStreamSegments.childNodes));
        changed = true;
    }
    const patchTarget = existingStreamSegments !== null && createdStreamSegments !== null ? { container: existingStreamSegments, nextContainer: createdStreamSegments } : { container: existingResponse, nextContainer: createdResponse };
    const contentChanged = patchAssistantBodyChildrenInPlace({
        container: patchTarget.container,
        nextContainer: patchTarget.nextContainer,
        assistantDomState: inputArguments.assistantDomState ?? null,
        disableInsertAnimation: terminalSensitiveStreamingBody || inputArguments.suppressInsertAnimations === true,
        patchExistingChild: patchStreamingTimelineSegmentInPlace
    });
    if (contentChanged === null) {
        return null;
    }
    if (contentChanged) {
        changed = true;
    }
    return changed;
};

export { canPatchAssistantMessageTextInPlace, hasCanonicalAssistantMessageTextBody, patchAssistantMessageTextInPlace };
