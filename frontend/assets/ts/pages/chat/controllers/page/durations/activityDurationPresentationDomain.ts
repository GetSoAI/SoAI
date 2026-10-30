/* SoAI - Settled-only activity duration DOM ownership [frontend/assets/ts/pages/chat/controllers/page/durations/activityDurationPresentationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncImageWidgetDuration, removeAssistantHeaderDuration, removeInlineActivityDuration, syncSettledInlineActivityDuration, type ChatActivityDurationDisplayMode } from '@features/chat/public.ts';
import { collectDurationActivities } from '@pages/chat/controllers/page/durations/activityDurationRegistrationDomain.ts';

const SETTLED_DURATION_ATTRIBUTE = 'data-settled-duration-ms';

const resolveSettledDurationMs = (activity: HTMLElement): number | null => {
    const rawValue = activity.getAttribute(SETTLED_DURATION_ATTRIBUTE);
    if (rawValue === null) {
        return null;
    }
    const durationMs = Number(rawValue);
    return Number.isInteger(durationMs) && durationMs >= 0 ? durationMs : null;
};

const reconcileActivityDurationPresentation = (root: Element, displayMode: ChatActivityDurationDisplayMode): void => {
    if (displayMode === 'all') {
        return;
    }
    for (const activity of collectDurationActivities(root)) {
        if (activity.classList.contains('assistant-image-widget')) {
            syncImageWidgetDuration(activity, 0, displayMode);
            continue;
        }
        const running = activity.classList.contains('inline-activity-status-running');
        if (activity.classList.contains('message-role-activity')) {
            if (running) {
                removeAssistantHeaderDuration(activity);
            }
            continue;
        }
        if (running) {
            removeInlineActivityDuration(activity);
            continue;
        }
        const settledDurationMs = resolveSettledDurationMs(activity);
        if (settledDurationMs !== null) {
            syncSettledInlineActivityDuration(activity, settledDurationMs, true);
        }
    }
};

export { reconcileActivityDurationPresentation };
