/* SoAI - Running activity duration discovery and registration data [frontend/assets/ts/pages/chat/controllers/page/durations/activityDurationRegistrationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import type { ChatActivityDurationDisplayMode } from '@features/chat/public.ts';

type RegisteredActivity = {
    type: 'inline' | 'assistantHeader';
    startedAtMs: number;
    nextDueEpochMs: number;
};

const RUNNING_ACTIVITY_SELECTOR = '.inline-activity.inline-activity-status-running[data-started-at-ms]:not(.message-role-activity)';
const RUNNING_ASSISTANT_HEADER_SELECTOR = '.message-role-activity.inline-activity-status-running[data-assistant-started-at-ms]';
const INLINE_ACTIVITY_SELECTOR = '.inline-activity';
const EXPANDABLE_ACTIVITY_SELECTOR = '.inline-activity:is(.inline-activity-type-tool, .inline-activity-type-thinking)';

const resolveStartedAtMs = (activity: HTMLElement): number | null => {
    const attributeName = activity.matches(RUNNING_ASSISTANT_HEADER_SELECTOR) ? 'data-assistant-started-at-ms' : 'data-started-at-ms';
    const rawValue = activity.getAttribute(attributeName);
    if (!rawValue) {
        return null;
    }
    const startedAtMs = Number(rawValue);
    return Number.isInteger(startedAtMs) && isEpochMsNumber(startedAtMs) ? startedAtMs : null;
};

const isInlineActivityExpanded = (activity: HTMLElement): boolean => {
    if (!activity.matches(EXPANDABLE_ACTIVITY_SELECTOR) || activity.hasAttribute('data-collapsing')) {
        return false;
    }
    const header = activity.firstElementChild;
    if (!(header instanceof HTMLElement) || header.getAttribute('aria-disabled') !== 'false') {
        return false;
    }
    return activity.getAttribute('data-collapsed') === 'false' || activity.getAttribute('data-details-open-requested') === 'true' || activity.getAttribute('data-details-open-pending') === 'true' || activity.getAttribute('data-details-loading') === 'true';
};

const isActivityDurationEligible = (activity: HTMLElement, displayMode: ChatActivityDurationDisplayMode): boolean => {
    if (displayMode === 'all') {
        return true;
    }
    if (displayMode === 'settledOnly') {
        return false;
    }
    if (activity.matches(RUNNING_ASSISTANT_HEADER_SELECTOR) || activity.classList.contains('message-role-activity')) {
        return false;
    }
    return isInlineActivityExpanded(activity);
};

const isRunningActivity = (element: Element, displayMode: ChatActivityDurationDisplayMode = 'all'): element is HTMLElement => {
    return element instanceof HTMLElement && (element.matches(RUNNING_ACTIVITY_SELECTOR) || element.matches(RUNNING_ASSISTANT_HEADER_SELECTOR)) && isActivityDurationEligible(element, displayMode);
};

const collectRunningActivities = (root: Element, displayMode: ChatActivityDurationDisplayMode = 'all'): HTMLElement[] => {
    const activities: HTMLElement[] = [];
    if (isRunningActivity(root, displayMode)) {
        activities.push(root);
    }
    for (const element of dom.resolveAll(`${RUNNING_ACTIVITY_SELECTOR}, ${RUNNING_ASSISTANT_HEADER_SELECTOR}`, root)) {
        if (element instanceof HTMLElement && isActivityDurationEligible(element, displayMode)) {
            activities.push(element);
        }
    }
    return activities;
};

const collectInlineActivities = (root: Element): HTMLElement[] => {
    const activities: HTMLElement[] = [];
    if (root instanceof HTMLElement && root.matches(INLINE_ACTIVITY_SELECTOR)) {
        activities.push(root);
    }
    for (const element of dom.resolveAll(INLINE_ACTIVITY_SELECTOR, root)) {
        if (element instanceof HTMLElement) {
            activities.push(element);
        }
    }
    return activities;
};

const intersectsViewport = (activity: HTMLElement, viewport: HTMLElement): boolean => {
    const activityRect = measureLayoutBox(activity);
    const viewportRect = measureLayoutBox(viewport);
    return activityRect.bottom > viewportRect.top && activityRect.top < viewportRect.bottom && activityRect.right > viewportRect.left && activityRect.left < viewportRect.right;
};

export { RUNNING_ASSISTANT_HEADER_SELECTOR, collectInlineActivities, collectRunningActivities, intersectsViewport, isActivityDurationEligible, isRunningActivity, resolveStartedAtMs };
export type { RegisteredActivity };
