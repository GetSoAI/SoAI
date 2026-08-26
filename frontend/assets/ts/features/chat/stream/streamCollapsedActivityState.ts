/* SoAI - Chat feature stream collapsed activity state [frontend/assets/ts/features/chat/stream/streamCollapsedActivityState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildInlineActivityDetailsDomKey } from '@features/chat/message/inlineActivityDetailsLifecycle.ts';
import { collectMatchingElements } from '@features/chat/stream/streamDomQueries.ts';

const readCollapsedActivityState = (root: Element): Map<string, boolean> => {
    const stateByActivityKey = new Map<string, boolean>();
    for (const element of collectMatchingElements(root, '.inline-activity[data-call-id][data-collapsed]')) {
        const key = buildInlineActivityDetailsDomKey(element);
        if (key === null) {
            continue;
        }
        stateByActivityKey.set(key, element.getAttribute('data-collapsed') === 'true');
    }
    return stateByActivityKey;
};

const applyCollapsedActivityState = (root: Element, stateByActivityKey: ReadonlyMap<string, boolean>): boolean => {
    if (stateByActivityKey.size === 0) {
        return false;
    }
    let changed = false;
    for (const element of collectMatchingElements(root, '.inline-activity[data-call-id]')) {
        const key = buildInlineActivityDetailsDomKey(element);
        if (key === null || !stateByActivityKey.has(key)) {
            continue;
        }
        const nextCollapsed = stateByActivityKey.get(key) === true ? 'true' : 'false';
        if (element.getAttribute('data-collapsed') !== nextCollapsed) {
            element.setAttribute('data-collapsed', nextCollapsed);
            changed = true;
        }
    }
    return changed;
};

export { applyCollapsedActivityState, readCollapsedActivityState };
