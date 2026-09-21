/* SoAI - Mobile activity duration DOM ownership [frontend/assets/ts/pages/chat/controllers/page/durations/activityDurationPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { removeAssistantHeaderDuration, removeInlineActivityDuration, syncRunningInlineActivityDuration, syncSettledInlineActivityDuration, type ChatActivityDurationDisplayMode } from '@features/chat/public.ts';
import { collectInlineActivities, isActivityDurationEligible } from '@pages/chat/controllers/page/durations/activityDurationRegistrationDomain.ts';

const ACTIVITY_DURATION_EXPANSION_ATTRIBUTES = ['data-collapsed', 'data-collapsing', 'data-details-open-requested', 'data-details-open-pending', 'data-details-loading'];
const SETTLED_DURATION_ATTRIBUTE = 'data-settled-duration-ms';

const resolveSettledDurationMs = (activity: HTMLElement): number | null => {
    const rawValue = activity.getAttribute(SETTLED_DURATION_ATTRIBUTE);
    if (rawValue === null) {
        return null;
    }
    const durationMs = Number(rawValue);
    return Number.isInteger(durationMs) && durationMs >= 0 ? durationMs : null;
};

const reconcileActivityDurationPresentation = (root: Element, displayMode: ChatActivityDurationDisplayMode, nowMs: number): void => {
    if (displayMode === 'all') {
        return;
    }
    for (const activity of collectInlineActivities(root)) {
        const running = activity.classList.contains('inline-activity-status-running');
        if (activity.classList.contains('message-role-activity')) {
            if (displayMode === 'expandedOnly' || running) {
                removeAssistantHeaderDuration(activity);
            }
            continue;
        }
        if (displayMode === 'settledOnly') {
            if (running) {
                removeInlineActivityDuration(activity);
                continue;
            }
            const settledDurationMs = resolveSettledDurationMs(activity);
            if (settledDurationMs !== null) {
                syncSettledInlineActivityDuration(activity, settledDurationMs, true);
            }
            continue;
        }
        if (!isActivityDurationEligible(activity, displayMode)) {
            removeInlineActivityDuration(activity);
            continue;
        }
        if (running) {
            syncRunningInlineActivityDuration(activity, nowMs);
            continue;
        }
        const settledDurationMs = resolveSettledDurationMs(activity);
        if (settledDurationMs !== null) {
            syncSettledInlineActivityDuration(activity, settledDurationMs);
        }
    }
};

export { ACTIVITY_DURATION_EXPANSION_ATTRIBUTES, reconcileActivityDurationPresentation };
