/* SoAI - Chat feature assistant subagent result details patching [frontend/assets/ts/features/chat/message/assistantSubagentResultDetailsPatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveHTMLElement, syncElementShell } from '@core/dom/patching.ts';
import { patchOrderedChildren } from '@core/dom/orderedChildPatching.ts';
import { patchStreamingKeyedChildren } from '@features/chat/message/assistantBodyKeyedReconciler.ts';
import { insertClonedElementWithAssistantState, patchElementChildren, removeElementWithAssistantState, replaceElementWithClonedAssistantState } from '@features/chat/message/assistantElementPatching.ts';
import type { StreamChildItem } from '@features/chat/message/assistantKeyedPatchContracts.ts';
import { ASSISTANT_BODY_KEY_ATTRIBUTE_NAME, ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { type ActivityPatchContext, type ActivityPatchHandler } from '@features/chat/message/assistantNestedActivityPatching.ts';
import { applyKeyedScrollableStateWithBottomDefault, readKeyedScrollableState } from '@features/chat/stream/streamScrollableState.ts';

type SubagentResultSectionType = 'status' | 'stream';
type TimelineItemCollection = { items: StreamChildItem[]; signatureByKey: Map<string, string> };

const resolveSubagentResultSectionType = (section: HTMLElement): SubagentResultSectionType | null => {
    if (section.classList.contains('inline-tool-subagent-status')) return 'status';
    if (section.classList.contains('inline-tool-subagent-stream')) return 'stream';
    return null;
};

const resolveStreamTimeline = (section: HTMLElement): HTMLElement | null => {
    return resolveHTMLElement(':scope > .inline-tool-subagent-stream-timeline', section);
};

const collectTimelineItems = (timeline: HTMLElement): TimelineItemCollection | null => {
    const items: StreamChildItem[] = [];
    const keys = new Set<string>();
    const signatureByKey = new Map<string, string>();
    for (const child of Array.from(timeline.children)) {
        if (!(child instanceof HTMLElement)) {
            return null;
        }
        const key = child.getAttribute(ASSISTANT_BODY_KEY_ATTRIBUTE_NAME);
        if (!key || !key.trim() || keys.has(key.trim())) {
            return null;
        }
        const normalizedKey = key.trim();
        const signatureAttribute = (child.getAttribute(ASSISTANT_BODY_SIGNATURE_ATTRIBUTE_NAME) ?? '').trim();
        if (!signatureAttribute) {
            return null;
        }
        keys.add(normalizedKey);
        items.push({
            key: normalizedKey,
            signature: signatureAttribute,
            element: child,
            signatureKind: 'attribute'
        });
        signatureByKey.set(normalizedKey, signatureAttribute);
    }
    return { items, signatureByKey };
};

const resolveEnclosingActivityDetails = (timeline: HTMLElement): HTMLElement | null => {
    const ancestor = timeline.closest('.inline-activity-details');
    return ancestor instanceof HTMLElement ? ancestor : null;
};

const patchSubagentStreamTimeline = (existingTimeline: HTMLElement, createdTimeline: HTMLElement, patchActivity: ActivityPatchHandler, context: ActivityPatchContext, applyStreamingReveal: boolean): boolean | null => {
    let changed = syncElementShell({ target: existingTimeline, source: createdTimeline });
    const createdCollection = collectTimelineItems(createdTimeline);
    const existingCollection = collectTimelineItems(existingTimeline);
    if (createdCollection === null || existingCollection === null) {
        return null;
    }
    const detailsScrollContainer = resolveEnclosingActivityDetails(existingTimeline);
    const preservedDetailsScroll = detailsScrollContainer ? readKeyedScrollableState(detailsScrollContainer) : null;
    const childrenPatchResult = patchStreamingKeyedChildren({
        container: existingTimeline,
        items: createdCollection.items,
        cachedMarkupByKey: null,
        cachedSignatureByKey: existingCollection.signatureByKey,
        policy: {
            nonReplaceableKeys: null,
            disableInsertAnimation: true,
            applyStreamingReveal,
            applyStreamingRevealToTextBlocks: applyStreamingReveal
        },
        assistantDomState: context.assistantDomState,
        patchExistingChild: patchActivity
    });
    if (childrenPatchResult.updated) {
        changed = true;
    }
    if (detailsScrollContainer) {
        applyKeyedScrollableStateWithBottomDefault(detailsScrollContainer, preservedDetailsScroll, detailsScrollContainer);
    }
    return changed;
};

const patchSubagentStreamSection = (existingSection: HTMLElement, createdSection: HTMLElement, patchActivity: ActivityPatchHandler, context: ActivityPatchContext, applyStreamingReveal: boolean): boolean => {
    let changed = syncElementShell({ target: existingSection, source: createdSection });
    const existingLabel = resolveHTMLElement(':scope > .inline-tool-label', existingSection);
    const createdLabel = resolveHTMLElement(':scope > .inline-tool-label', createdSection);
    const existingTimeline = resolveStreamTimeline(existingSection);
    const createdTimeline = resolveStreamTimeline(createdSection);
    if (!existingLabel || !createdLabel || !existingTimeline || !createdTimeline) {
        return patchElementChildren(existingSection, createdSection, context) || changed;
    }
    if (patchElementChildren(existingLabel, createdLabel, context)) {
        changed = true;
    }
    const timelineChanged = patchSubagentStreamTimeline(existingTimeline, createdTimeline, patchActivity, context, applyStreamingReveal);
    if (timelineChanged === null) {
        return patchElementChildren(existingSection, createdSection, context) || changed;
    }
    return timelineChanged || changed;
};

const patchSubagentResultSection = (existingSection: HTMLElement, createdSection: HTMLElement, patchActivity: ActivityPatchHandler, context: ActivityPatchContext, applyStreamingReveal: boolean): boolean | null => {
    const existingMeta = resolveHTMLElement(':scope > .inline-tool-subagent-result-meta', existingSection);
    const createdMeta = resolveHTMLElement(':scope > .inline-tool-subagent-result-meta', createdSection);
    if (!existingMeta && !createdMeta) {
        return null;
    }
    if (!existingMeta || !createdMeta) {
        replaceElementWithClonedAssistantState(existingSection, createdSection, context);
        return true;
    }
    const sectionChanged = syncElementShell({ target: existingSection, source: createdSection });
    const metaChanged = syncElementShell({ target: existingMeta, source: createdMeta });
    return (
        patchOrderedChildren({
            existingParent: existingMeta,
            createdParent: createdMeta,
            resolveChildKey: resolveSubagentResultSectionType,
            insertChild: (parent, child, anchor) => insertClonedElementWithAssistantState(parent, child, anchor, context),
            patchChild: (existingChild, createdChild, key) => (key === 'stream' ? patchSubagentStreamSection(existingChild, createdChild, patchActivity, context, applyStreamingReveal) : patchElementChildren(existingChild, createdChild, context)),
            removeChild: (existingChild) => removeElementWithAssistantState(existingChild, context),
            replaceUnsupportedChildren: () => {
                return patchElementChildren(existingSection, createdSection, context);
            }
        }) ||
        sectionChanged ||
        metaChanged
    );
};

export { patchSubagentResultSection };
