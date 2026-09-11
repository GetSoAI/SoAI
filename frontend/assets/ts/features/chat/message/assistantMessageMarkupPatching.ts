/* SoAI - Chat feature assistant message markup patching [frontend/assets/ts/features/chat/message/assistantMessageMarkupPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncAttributes, syncClass } from '@core/dom/patching.ts';
import { patchElementChildren, replaceElementWithClonedAssistantState } from '@features/chat/message/assistantElementPatching.ts';
import { patchAssistantMessageHeader } from '@features/chat/message/assistantMessageHeaderPatching.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { parseRenderedMarkupRoot } from '@features/chat/message/renderedMarkupRoot.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { applyAssistantMessageTextUpdate } from '@features/chat/message/assistantMessageTextDomApply.ts';
import type { AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { patchAssistantMessageActionsInPlace } from '@features/chat/message/assistantMessageActionsPatching.ts';
import { applyChatMessageEnterAnimation, type ChatMessageInsertAnimationOptions } from '@features/chat/message/messageMotion.ts';
import { hasCanonicalAssistantMessageTextBody } from '@features/chat/message/assistantMessageTextPatching.ts';

type AssistantMessagePatchResult = {
    supported: boolean;
    changed: boolean;
    requiresPostRender: boolean;
};

type AssistantMessageSurfacePatchMode = 'full' | 'preserveText';

const preservedRootAttributeNames = new Set<string>(['data-id']);

const patchResolvedAssistantMessageInPlace = (inputArguments: { existingMessageRoot: HTMLElement; replacement: HTMLElement; mode: AssistantMessageSurfacePatchMode; options: ChatMessageInsertAnimationOptions; assistantDomState?: AssistantDomStatePreservation | null; forceTextPatch?: boolean; activityToggle?: boolean }): AssistantMessagePatchResult => {
    if (!inputArguments.replacement.classList.contains('chat-message') || !inputArguments.replacement.classList.contains('assistant')) {
        return { supported: false, changed: false, requiresPostRender: false };
    }
    const existingParts = resolveAssistantMessageParts(inputArguments.existingMessageRoot);
    const createdParts = resolveAssistantMessageParts(inputArguments.replacement);
    if (!existingParts || !createdParts) {
        return { supported: false, changed: false, requiresPostRender: false };
    }

    const { avatar: existingAvatar, content: existingContent, header: existingHeader, text: existingText, actions: existingActions } = existingParts;
    const { avatar: createdAvatar, content: createdContent, header: createdHeader, text: createdText, actions: createdActions } = createdParts;
    if (!hasCanonicalAssistantMessageTextBody(createdText)) {
        throw new Error('Assistant message reconcile rejected a non-canonical keyed body without mutating the live tree.');
    }
    const canPatchTextInPlace = hasCanonicalAssistantMessageTextBody(existingText);
    if (inputArguments.activityToggle === true) {
        if (!canPatchTextInPlace) {
            throw new Error('Activity presentation requires a canonical assistant body');
        }
        const changed = applyAssistantMessageTextUpdate({ existingText, createdText, suppressInsertAnimations: true, preserveActiveStreamingText: true, assistantDomState: inputArguments.assistantDomState ?? null });
        return { supported: true, changed, requiresPostRender: changed };
    }
    let changed = false;

    if (syncClass(inputArguments.existingMessageRoot, inputArguments.replacement)) {
        changed = true;
    }
    if (syncAttributes({ target: inputArguments.existingMessageRoot, source: inputArguments.replacement, preservedAttributeNames: preservedRootAttributeNames })) {
        changed = true;
    }
    if (syncClass(existingContent, createdContent)) {
        changed = true;
    }

    if (existingAvatar && createdAvatar) {
        if (patchElementChildren(existingAvatar, createdAvatar)) {
            changed = true;
        }
    } else if (!existingAvatar && createdAvatar) {
        applyChatMessageEnterAnimation(createdAvatar, inputArguments.options);
        inputArguments.existingMessageRoot.insertBefore(createdAvatar, existingContent);
        changed = true;
    } else if (existingAvatar && !createdAvatar) {
        existingAvatar.remove();
        changed = true;
    }

    if (syncAttributes({ target: existingContent, source: createdContent })) {
        changed = true;
    }

    if (existingHeader && createdHeader) {
        if (patchAssistantMessageHeader(existingHeader, createdHeader)) {
            changed = true;
        }
    } else if (!existingHeader && createdHeader) {
        applyChatMessageEnterAnimation(createdHeader, inputArguments.options);
        existingContent.insertBefore(createdHeader, existingText);
        changed = true;
    } else if (existingHeader && !createdHeader) {
        existingHeader.remove();
        changed = true;
    }

    if (existingActions && createdActions) {
        if (patchAssistantMessageActionsInPlace(existingActions, createdActions, inputArguments.options)) {
            changed = true;
        }
    } else if (!existingActions && createdActions) {
        applyChatMessageEnterAnimation(createdActions, inputArguments.options);
        existingContent.appendChild(createdActions);
        changed = true;
    } else if (existingActions && !createdActions) {
        existingActions.remove();
        changed = true;
    }

    let requiresPostRender = false;
    if (inputArguments.mode !== 'preserveText' || inputArguments.forceTextPatch === true) {
        if (!canPatchTextInPlace) {
            replaceElementWithClonedAssistantState(existingText, createdText, {
                assistantDomState: inputArguments.assistantDomState ?? null
            });
            changed = true;
            requiresPostRender = true;
        } else {
            const textPatchChanged = applyAssistantMessageTextUpdate({
                existingText,
                createdText,
                suppressInsertAnimations: inputArguments.options.suppressInsertAnimations === true,
                ...(inputArguments.assistantDomState !== undefined ? { assistantDomState: inputArguments.assistantDomState } : {})
            });
            if (textPatchChanged) {
                changed = true;
                requiresPostRender = true;
            }
        }
    }

    return { supported: true, changed, requiresPostRender };
};

const applyParsedAssistantMessageRoot = (inputArguments: { existingMessageRoot: HTMLElement; replacement: HTMLElement; mode?: AssistantMessageSurfacePatchMode; suppressInsertAnimations?: boolean; assistantDomState?: AssistantDomStatePreservation | null; forceTextPatch?: boolean; activityToggle?: boolean }): { root: HTMLElement; changed: boolean; requiresPostRender: boolean } => {
    const patchResult = patchResolvedAssistantMessageInPlace({
        existingMessageRoot: inputArguments.existingMessageRoot,
        replacement: inputArguments.replacement,
        mode: inputArguments.mode ?? 'full',
        options: {
            suppressInsertAnimations: inputArguments.suppressInsertAnimations === true
        },
        ...(inputArguments.assistantDomState !== undefined ? { assistantDomState: inputArguments.assistantDomState } : {}),
        ...(inputArguments.forceTextPatch === true ? { forceTextPatch: true } : {}),
        ...(inputArguments.activityToggle === true ? { activityToggle: true } : {})
    });
    if (!patchResult.supported) {
        throw new Error('Assistant message reconcile requires a canonical assistant DOM shape.');
    }
    return {
        root: inputArguments.existingMessageRoot,
        changed: patchResult.changed,
        requiresPostRender: patchResult.requiresPostRender
    };
};

const applyRenderedAssistantMessageRoot = (inputArguments: { existingMessageRoot: HTMLElement; nextMarkup: TrustedHtml; mode?: AssistantMessageSurfacePatchMode; suppressInsertAnimations?: boolean; assistantDomState?: AssistantDomStatePreservation | null; forceTextPatch?: boolean; activityToggle?: boolean }): { root: HTMLElement; changed: boolean; requiresPostRender: boolean } => {
    const replacement = parseRenderedMarkupRoot({
        documentRef: inputArguments.existingMessageRoot.ownerDocument,
        nextMarkup: inputArguments.nextMarkup,
        context: inputArguments.existingMessageRoot.ownerDocument,
        failureMessage: 'Assistant message reconcile failed to parse rendered markup.'
    });
    return applyParsedAssistantMessageRoot({
        existingMessageRoot: inputArguments.existingMessageRoot,
        replacement,
        ...(inputArguments.mode !== undefined ? { mode: inputArguments.mode } : {}),
        ...(inputArguments.suppressInsertAnimations !== undefined ? { suppressInsertAnimations: inputArguments.suppressInsertAnimations } : {}),
        ...(inputArguments.assistantDomState !== undefined ? { assistantDomState: inputArguments.assistantDomState } : {}),
        ...(inputArguments.forceTextPatch === true ? { forceTextPatch: true } : {}),
        ...(inputArguments.activityToggle === true ? { activityToggle: true } : {})
    });
};

export { applyParsedAssistantMessageRoot, applyRenderedAssistantMessageRoot };
