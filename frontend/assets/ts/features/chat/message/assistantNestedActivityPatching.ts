/* SoAI - Chat feature assistant nested activity patching [frontend/assets/ts/features/chat/message/assistantNestedActivityPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncElementShell } from '@core/dom/patching.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { insertClonedElementWithAssistantState, patchElementChildren, removeElementWithAssistantState, replaceElementWithClonedAssistantState, type AssistantElementPatchContext } from '@features/chat/message/assistantElementPatching.ts';
import type { AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';

type ActivityPatchResult = { patched: boolean; detailsChanged: boolean; retainedSignature?: string };
type ActivityPatchContext = AssistantElementPatchContext;
type ActivityPatchArguments = {
    existing: HTMLElement;
    created: HTMLElement;
    assistantDomState: AssistantDomStatePreservation | null;
    applyStreamingReveal?: boolean;
};
type ActivityPatchHandler = (inputArguments: ActivityPatchArguments) => ActivityPatchResult;

const EMPTY_ACTIVITY_PATCH_CONTEXT: ActivityPatchContext = { assistantDomState: null };

const resolveActivityChildKey = (child: HTMLElement): string | null => {
    if (!child.classList.contains('inline-activity') && !child.classList.contains('inline-action-update')) {
        return null;
    }
    const callId = child.getAttribute('data-call-id');
    if (!callId || !callId.trim()) {
        return null;
    }
    const timelineSequenceIndex = child.getAttribute('data-timeline-sequence-index');
    const timelineSequenceSuffix = timelineSequenceIndex && timelineSequenceIndex.trim() ? timelineSequenceIndex.trim() : '';
    if (child.classList.contains('inline-action-update')) {
        return timelineSequenceSuffix ? `inline_action_update:${callId.trim()}:${timelineSequenceSuffix}` : `inline_action_update:${callId.trim()}`;
    }
    if (child.classList.contains('inline-activity-type-thinking')) {
        return timelineSequenceSuffix ? `inline_thinking_activity:${callId.trim()}:${timelineSequenceSuffix}` : `inline_thinking_activity:${callId.trim()}`;
    }
    return `inline_tool_activity:${callId.trim()}`;
};

const patchResolvedInlineActivityGroup = (existingGroup: HTMLElement, createdGroup: HTMLElement, patchActivity: ActivityPatchHandler, context: ActivityPatchContext = EMPTY_ACTIVITY_PATCH_CONTEXT): boolean => {
    const changed = syncElementShell({ target: existingGroup, source: createdGroup });
    return (
        patchOrderedChildren({
            existingParent: existingGroup,
            createdParent: createdGroup,
            resolveChildKey: resolveActivityChildKey,
            insertChild: (parent, child, anchor) => insertClonedElementWithAssistantState(parent, child, anchor, context),
            patchChild: (existingItem, createdItem) => {
                const patched = patchActivity({
                    existing: existingItem,
                    created: createdItem,
                    assistantDomState: context.assistantDomState
                });
                if (!patched.patched) {
                    replaceElementWithClonedAssistantState(existingItem, createdItem, context);
                    return true;
                }
                return patched.detailsChanged;
            },
            removeChild: (existingItem) => removeElementWithAssistantState(existingItem, context),
            replaceUnsupportedChildren: () => patchElementChildren(existingGroup, createdGroup, context)
        }) || changed
    );
};

export { patchResolvedInlineActivityGroup, type ActivityPatchContext, type ActivityPatchHandler };
