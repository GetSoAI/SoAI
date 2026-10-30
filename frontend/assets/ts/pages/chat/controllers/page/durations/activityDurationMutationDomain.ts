/* SoAI - Activity duration mutation discovery [frontend/assets/ts/pages/chat/controllers/page/durations/activityDurationMutationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { collectDurationActivities } from '@pages/chat/controllers/page/durations/activityDurationRegistrationDomain.ts';

const ACTIVITY_DURATION_DISCOVERY_ATTRIBUTES = ['class', 'data-started-at-ms', 'data-assistant-started-at-ms', 'data-image-widget-status', 'data-settled-duration-ms'];

type ActivityDurationMutationImpact = {
    roots: Set<HTMLElement>;
    requiresPrune: boolean;
};

const elementContainsDurationActivity = (element: HTMLElement): boolean => collectDurationActivities(element).length > 0;

const resolveActivityDurationMutationImpact = (records: readonly MutationRecord[]): ActivityDurationMutationImpact => {
    const roots = new Set<HTMLElement>();
    let requiresPrune = false;
    for (const record of records) {
        if (record.type === 'attributes') {
            const target = record.target;
            if (target instanceof HTMLElement && (target.classList.contains('inline-activity') || target.classList.contains('assistant-image-widget'))) {
                roots.add(target);
                requiresPrune = true;
            }
            continue;
        }
        for (const removedNode of Array.from(record.removedNodes)) {
            if (removedNode instanceof HTMLElement && elementContainsDurationActivity(removedNode)) {
                requiresPrune = true;
            }
        }
        for (const addedNode of Array.from(record.addedNodes)) {
            if (addedNode instanceof HTMLElement && elementContainsDurationActivity(addedNode)) {
                roots.add(addedNode);
            }
        }
    }
    return { roots, requiresPrune };
};

export { ACTIVITY_DURATION_DISCOVERY_ATTRIBUTES, resolveActivityDurationMutationImpact };
