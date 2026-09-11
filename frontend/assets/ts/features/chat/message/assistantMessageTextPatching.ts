/* SoAI - Chat feature assistant message text patching [frontend/assets/ts/features/chat/message/assistantMessageTextPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncAttributes, syncClass } from '@core/dom/patching.ts';
import type { AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { patchAssistantBodyChildrenInPlace } from '@features/chat/message/assistantBodyKeyedReconciler.ts';
import { patchStreamingTimelineSegmentInPlace } from '@features/chat/message/assistantTimelineSegmentPatching.ts';
import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, buildAssistantBodyItems, formatAssistantBodySegmentSignature, resolveAssistantMessageResponseRoot } from '@features/chat/message/assistantMessageMarkupParts.ts';
import type { ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';
import { isRetainedLoadingContentElement, resolveDirectCollapsedLoadingContent, resolveDirectCollapsedLoadingSummary, COLLAPSED_LOADING_CONTENT_DATA_ATTR, COLLAPSED_LOADING_CONTENT_DATA_VALUE } from '@features/chat/message/messageview/loadingActivityCollapsePolicy.ts';
import { hasStreamSegments, resolveDirectStreamSegments } from '@features/chat/stream/streamSegmentsMarker.ts';

const hasTerminalSensitiveStreamingBody = (response: HTMLElement): boolean => {
    return hasStreamSegments(response) || resolveDirectCollapsedLoadingSummary(response) !== null || resolveDirectCollapsedLoadingContent(response) !== null;
};

const prepareLoadingContentLayout = (existingResponse: HTMLElement, createdResponse: HTMLElement): boolean => {
    const existingWrapper = resolveDirectCollapsedLoadingContent(existingResponse);
    const createdWrapper = resolveDirectCollapsedLoadingContent(createdResponse);
    if (existingWrapper instanceof HTMLElement && !(createdWrapper instanceof HTMLElement)) {
        const streamSegments = resolveDirectStreamSegments(existingWrapper);
        if (streamSegments !== null) {
            streamSegments.replaceWith(...Array.from(streamSegments.childNodes));
        }
        existingWrapper.replaceWith(...Array.from(existingWrapper.childNodes));
        return true;
    }
    if (existingWrapper !== null || !(createdWrapper instanceof HTMLElement)) {
        return false;
    }
    const streamSegments = resolveDirectStreamSegments(existingResponse);
    if (streamSegments !== null && existingResponse.children.length === 1) {
        streamSegments.replaceWith(...Array.from(streamSegments.childNodes));
    }
    const contentChildren = Array.from(existingResponse.children).filter((child): child is HTMLElement => child instanceof HTMLElement && isRetainedLoadingContentElement(child));
    const wrapper = existingResponse.ownerDocument.createElement('div');
    wrapper.setAttribute(COLLAPSED_LOADING_CONTENT_DATA_ATTR, COLLAPSED_LOADING_CONTENT_DATA_VALUE);
    const wrapperKey = createdWrapper.getAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME);
    if (!wrapperKey) {
        throw new Error('Validated collapsed loading content is missing its key');
    }
    wrapper.setAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, wrapperKey);
    existingResponse.insertBefore(wrapper, contentChildren[0] ?? null);
    for (const child of contentChildren) {
        wrapper.appendChild(child);
    }
    wrapper.setAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME, formatAssistantBodySegmentSignature(wrapper.innerHTML));
    return true;
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
    const collapsedContent = resolveDirectCollapsedLoadingContent(response);
    const collapsedSummary = resolveDirectCollapsedLoadingSummary(response);
    if ((collapsedContent !== null && collapsedSummary === null) || (streamSegments !== null && collapsedContent !== null)) {
        return null;
    }
    if (collapsedContent instanceof HTMLElement && buildAssistantBodyItems(resolveDirectStreamSegments(collapsedContent) ?? collapsedContent) === null) {
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
        createdCollapsedContent: resolveDirectCollapsedLoadingContent(created.response)
    };
};

const hasCanonicalAssistantMessageTextBody = (textRoot: HTMLElement): boolean => resolveAssistantTextPatchRoot(textRoot) !== null;

const canPatchAssistantMessageTextInPlace = (existingText: HTMLElement, createdText: HTMLElement): boolean => resolveAssistantTextPatchRoots(existingText, createdText) !== null;

const patchAssistantMessageTextInPlace = (inputArguments: { existingText: HTMLElement; createdText: HTMLElement; preserveActiveStreamingText?: boolean; suppressInsertAnimations?: ChatMessageInsertAnimationOptions['suppressInsertAnimations']; assistantDomState?: AssistantDomStatePreservation | null }): boolean | null => {
    const roots = resolveAssistantTextPatchRoots(inputArguments.existingText, inputArguments.createdText);
    if (roots === null) {
        return null;
    }
    const { existingResponse, createdResponse, createdStreamSegments, createdCollapsedContent } = roots;
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
    if (prepareLoadingContentLayout(existingResponse, createdResponse)) {
        changed = true;
    }
    const existingStreamSegments = resolveDirectStreamSegments(existingResponse);
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
        patchExistingChild: (patchArguments) => patchStreamingTimelineSegmentInPlace({ ...patchArguments, preserveActiveStreamingText: inputArguments.preserveActiveStreamingText === true })
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
