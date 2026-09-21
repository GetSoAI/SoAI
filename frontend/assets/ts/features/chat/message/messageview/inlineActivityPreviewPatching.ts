/* SoAI - Chat feature inline activity preview patching [frontend/assets/ts/features/chat/message/messageview/inlineActivityPreviewPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { haveEqualChildNodes, syncAttribute, syncClass } from '@core/dom/patching.ts';
import { STREAMED_PREVIEW_ATTRIBUTE_NAMES } from '@features/chat/message/messageview/inlineActivityText.ts';
import { resolveHeaderChildren, resolveInlineActivityPreviewText } from '@features/chat/message/messageview/inlineActivityHeaderChildrenDomOps.ts';

const haveSameClassSet = (left: HTMLElement, right: HTMLElement): boolean => {
    const leftClasses = left.classList;
    const rightClasses = right.classList;
    if (leftClasses.length !== rightClasses.length) {
        return false;
    }
    for (const className of Array.from(leftClasses)) {
        if (!rightClasses.contains(className)) {
            return false;
        }
    }
    return true;
};

const isStreamedPreviewNode = (preview: HTMLElement | null): preview is HTMLElement => {
    return preview?.getAttribute(STREAMED_PREVIEW_ATTRIBUTE_NAMES.root) === 'true';
};

const patchStreamedPreview = (existingPreview: HTMLElement, createdPreview: HTMLElement): boolean => {
    let changed = false;
    if (syncClass(existingPreview, createdPreview)) {
        changed = true;
    }
    if (syncAttribute({ target: existingPreview, source: createdPreview, name: STREAMED_PREVIEW_ATTRIBUTE_NAMES.root })) {
        changed = true;
    }
    if (syncAttribute({ target: existingPreview, source: createdPreview, name: STREAMED_PREVIEW_ATTRIBUTE_NAMES.status })) {
        changed = true;
    }
    if (syncAttribute({ target: existingPreview, source: createdPreview, name: STREAMED_PREVIEW_ATTRIBUTE_NAMES.latest })) {
        changed = true;
    }
    const existingText = resolveInlineActivityPreviewText(existingPreview);
    const createdText = resolveInlineActivityPreviewText(createdPreview);
    if (!existingText || !createdText) {
        return changed;
    }
    if (!createdText.textContent?.trim()) {
        return changed;
    }
    if (syncClass(existingText, createdText)) {
        changed = true;
    }
    const status = createdPreview.getAttribute(STREAMED_PREVIEW_ATTRIBUTE_NAMES.status);
    if (status === 'running') {
        return changed;
    }
    if (syncAttribute({ target: existingPreview, source: createdPreview, name: STREAMED_PREVIEW_ATTRIBUTE_NAMES.visible })) {
        changed = true;
    }
    if (existingText.textContent !== createdText.textContent) {
        existingText.textContent = createdText.textContent;
        changed = true;
    }
    return changed;
};

const patchInlineActivityPreviewNode = (existingHeader: HTMLElement, createdHeader: HTMLElement): boolean => {
    const existingChildren = resolveHeaderChildren(existingHeader);
    const createdChildren = resolveHeaderChildren(createdHeader);
    const existingPreview = existingChildren.preview;
    const createdPreview = createdChildren.preview;
    if (!createdPreview) {
        if (!existingPreview) {
            return false;
        }
        existingPreview.remove();
        return true;
    }
    if (!existingPreview) {
        const cloned = createdPreview.cloneNode(true);
        const anchor = existingChildren.separatorDot ?? existingChildren.name;
        if (anchor) {
            existingHeader.insertBefore(cloned, anchor.nextSibling);
            return true;
        }
        existingHeader.appendChild(cloned);
        return true;
    }
    const existingIsStreamedPreview = isStreamedPreviewNode(existingPreview);
    const createdIsStreamedPreview = isStreamedPreviewNode(createdPreview);
    if (existingIsStreamedPreview && createdIsStreamedPreview) {
        return patchStreamedPreview(existingPreview, createdPreview);
    }
    const existingHidden = existingPreview.hasAttribute('hidden');
    const createdHidden = createdPreview.hasAttribute('hidden');
    if (existingIsStreamedPreview !== createdIsStreamedPreview || !haveSameClassSet(existingPreview, createdPreview) || existingHidden !== createdHidden || !haveEqualChildNodes(existingPreview, createdPreview)) {
        existingPreview.replaceWith(createdPreview.cloneNode(true));
        return true;
    }
    return false;
};

export { patchInlineActivityPreviewNode };
