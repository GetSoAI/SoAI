/* SoAI - Activity duration mutation discovery [frontend/assets/ts/pages/chat/controllers/page/durations/activityDurationMutationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { collectInlineActivities } from '@pages/chat/controllers/page/durations/activityDurationRegistrationDomain.ts';
import { ACTIVITY_DURATION_EXPANSION_ATTRIBUTES } from '@pages/chat/controllers/page/durations/activityDurationPresentationDomain.ts';

const ACTIVITY_DURATION_DISCOVERY_ATTRIBUTES = [...ACTIVITY_DURATION_EXPANSION_ATTRIBUTES, 'class', 'data-started-at-ms', 'data-assistant-started-at-ms', 'aria-disabled'];

type ActivityDurationMutationImpact = {
    roots: Set<HTMLElement>;
    requiresPrune: boolean;
};

const elementContainsInlineActivity = (element: HTMLElement): boolean => collectInlineActivities(element).length > 0;

const resolveActivityDurationMutationImpact = (records: readonly MutationRecord[]): ActivityDurationMutationImpact => {
    const roots = new Set<HTMLElement>();
    let requiresPrune = false;
    for (const record of records) {
        if (record.type === 'attributes') {
            const target = record.target;
            if (target instanceof HTMLElement && target.classList.contains('inline-activity')) {
                roots.add(target);
                requiresPrune = true;
            } else if (target instanceof HTMLElement && record.attributeName === 'aria-disabled' && target.parentElement?.classList.contains('inline-activity') && target.parentElement.firstElementChild === target) {
                roots.add(target.parentElement);
                requiresPrune = true;
            }
            continue;
        }
        for (const removedNode of Array.from(record.removedNodes)) {
            if (removedNode instanceof HTMLElement && elementContainsInlineActivity(removedNode)) {
                requiresPrune = true;
            }
        }
        for (const addedNode of Array.from(record.addedNodes)) {
            if (addedNode instanceof HTMLElement && elementContainsInlineActivity(addedNode)) {
                roots.add(addedNode);
            }
        }
    }
    return { roots, requiresPrune };
};

export { ACTIVITY_DURATION_DISCOVERY_ATTRIBUTES, resolveActivityDurationMutationImpact };
