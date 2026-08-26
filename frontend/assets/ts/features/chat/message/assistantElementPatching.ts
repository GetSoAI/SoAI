/* SoAI - Chat feature assistant element patching [frontend/assets/ts/features/chat/message/assistantElementPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { haveEqualChildNodes, replaceChildrenIfChanged, syncElementShell } from '@core/dom/patching.ts';
import { discardAssistantDomNode, insertOrReplaceAssistantDomChild, reconcileAssistantDom } from '@features/chat/message/assistantDomReconciler.ts';
import { resolveAssistantDomStateForPatch, type AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';

type AssistantElementPatchContext = {
    assistantDomState: AssistantDomStatePreservation | null;
};

const EMPTY_ASSISTANT_ELEMENT_PATCH_CONTEXT: AssistantElementPatchContext = {
    assistantDomState: null
};

const cloneElementForPatch = (source: HTMLElement): HTMLElement => {
    const cloned = source.cloneNode(true);
    if (!(cloned instanceof HTMLElement)) {
        throw new Error('Assistant element patching failed to clone an element.');
    }
    return cloned;
};

const insertClonedElementWithAssistantState = (parent: HTMLElement, source: HTMLElement, anchor: ChildNode | null, context: AssistantElementPatchContext): HTMLElement => {
    const cloned = cloneElementForPatch(source);
    const assistantDomState = resolveAssistantDomStateForPatch(parent, context.assistantDomState);
    if (assistantDomState) {
        return insertOrReplaceAssistantDomChild({ parent, element: cloned, anchor, state: assistantDomState });
    }
    parent.insertBefore(cloned, anchor);
    return cloned;
};

const replaceElementWithClonedAssistantState = (existing: HTMLElement, source: HTMLElement, context: AssistantElementPatchContext): HTMLElement => {
    const cloned = cloneElementForPatch(source);
    const assistantDomState = resolveAssistantDomStateForPatch(existing, context.assistantDomState);
    if (assistantDomState) {
        const parent = existing.parentNode;
        if (!parent) {
            throw new Error('Assistant element replacement requires an attached target.');
        }
        return insertOrReplaceAssistantDomChild({ parent, element: cloned, anchor: existing, state: assistantDomState, target: existing });
    }
    existing.replaceWith(cloned);
    return cloned;
};

const removeElementWithAssistantState = (existing: HTMLElement, context: AssistantElementPatchContext): void => {
    if (context.assistantDomState !== null) {
        discardAssistantDomNode(existing, context.assistantDomState);
    }
    existing.remove();
};

const patchElementChildren = (existingElement: HTMLElement, createdElement: HTMLElement, context: AssistantElementPatchContext = EMPTY_ASSISTANT_ELEMENT_PATCH_CONTEXT): boolean => {
    let changed = syncElementShell({ target: existingElement, source: createdElement });
    if (!haveEqualChildNodes(existingElement, createdElement)) {
        const assistantDomState = resolveAssistantDomStateForPatch(existingElement, context.assistantDomState);
        if (assistantDomState) {
            reconcileAssistantDom({ target: existingElement, source: createdElement, mode: 'messageBodyPatch', state: assistantDomState });
        } else {
            replaceChildrenIfChanged(existingElement, createdElement);
        }
        changed = true;
    }
    return changed;
};

export { insertClonedElementWithAssistantState, patchElementChildren, removeElementWithAssistantState, replaceElementWithClonedAssistantState };
export type { AssistantElementPatchContext };
