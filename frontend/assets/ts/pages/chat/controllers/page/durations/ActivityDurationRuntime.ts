/* SoAI - Page-owned adaptive visible activity duration runtime [frontend/assets/ts/pages/chat/controllers/page/durations/ActivityDurationRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncRunningAssistantHeaderDuration, syncRunningInlineActivityDuration, type ChatActivityDurationDisplayMode } from '@features/chat/public.ts';
import { ActivityDurationTickerState } from '@pages/chat/controllers/page/durations/ActivityDurationTickerState.ts';
import { RUNNING_ASSISTANT_HEADER_SELECTOR, collectRunningActivities, intersectsViewport, isRunningActivity, resolveStartedAtMs, type RegisteredActivity } from '@pages/chat/controllers/page/durations/activityDurationRegistrationDomain.ts';
import { reconcileActivityDurationPresentation } from '@pages/chat/controllers/page/durations/activityDurationPresentationDomain.ts';
import { ACTIVITY_DURATION_DISCOVERY_ATTRIBUTES, resolveActivityDurationMutationImpact } from '@pages/chat/controllers/page/durations/activityDurationMutationDomain.ts';

type ActivityDurationObserver = {
    observe: (element: Element) => void;
    unobserve: (element: Element) => void;
    disconnect: () => void;
};

type ActivityDurationObserverFactory = (callback: IntersectionObserverCallback, viewport: HTMLElement) => ActivityDurationObserver;

type ActivityDurationRuntimeOptions = {
    viewport: HTMLElement;
    conversationId: string;
    observerFactory?: ActivityDurationObserverFactory;
    nowEpochMs: () => number;
    nowMonotonicMs: () => number;
    setTimer: (callback: () => void, delayMs: number) => number;
    clearTimer: (timerId: number) => void;
    getDisplayMode: () => ChatActivityDurationDisplayMode;
    documentRef?: Document;
};

const WHOLE_SECOND_INTERVAL_MS = 1_000;

const createBrowserObserver: ActivityDurationObserverFactory = (callback, viewport) => new IntersectionObserver(callback, { root: viewport });

class ActivityDurationRuntime {
    readonly #options: ActivityDurationRuntimeOptions;
    readonly #observer: ActivityDurationObserver;
    readonly #registered = new Map<HTMLElement, RegisteredActivity>();
    readonly #intersecting = new Set<HTMLElement>();
    readonly #tickerHealth = new ActivityDurationTickerState();
    readonly #visibilityListener: () => void;
    readonly #mutationObserver: MutationObserver;
    #generation = 1;
    #timerId: number | null = null;
    #scheduledDueEpochMs: number | null = null;
    #expectedDeadlineMs: number | null = null;
    #disposed = false;

    constructor(options: ActivityDurationRuntimeOptions) {
        this.#options = options;
        const generation = this.#generation;
        this.#observer = (options.observerFactory ?? createBrowserObserver)((entries) => this.#handleIntersections(entries, generation), options.viewport);
        this.#visibilityListener = () => this.#handleVisibilityChange(generation);
        (options.documentRef ?? document).addEventListener('visibilitychange', this.#visibilityListener);
        this.#mutationObserver = new MutationObserver((records) => this.#handleMutations(records, generation));
        this.#mutationObserver.observe(options.viewport, { attributes: true, childList: true, subtree: true, attributeFilter: ACTIVITY_DURATION_DISCOVERY_ATTRIBUTES });
    }

    reconcile(root: Element, conversationId: string): void {
        if (this.#disposed || conversationId !== this.#options.conversationId) {
            return;
        }
        const displayMode = this.#options.getDisplayMode();
        this.#prune(displayMode);
        this.#reconcile(root, conversationId, displayMode);
        this.#schedule();
    }

    #reconcile(root: Element, conversationId: string, displayMode: ChatActivityDurationDisplayMode): void {
        if (this.#disposed || conversationId !== this.#options.conversationId) {
            return;
        }
        const nowEpochMs = this.#options.nowEpochMs();
        reconcileActivityDurationPresentation(root, displayMode, nowEpochMs);
        for (const activity of collectRunningActivities(root, displayMode)) {
            if (!this.#owns(activity, displayMode)) {
                continue;
            }
            const startedAtMs = resolveStartedAtMs(activity);
            if (startedAtMs === null) {
                continue;
            }
            const existing = this.#registered.get(activity);
            if (existing) {
                if (existing.startedAtMs !== startedAtMs) {
                    existing.startedAtMs = startedAtMs;
                    existing.nextDueEpochMs = nowEpochMs;
                    if (this.#intersecting.has(activity)) {
                        this.#syncActivity(activity, existing.nextDueEpochMs, displayMode);
                    }
                }
                continue;
            }
            this.#registered.set(activity, {
                type: activity.matches(RUNNING_ASSISTANT_HEADER_SELECTOR) ? 'assistantHeader' : 'inline',
                startedAtMs,
                nextDueEpochMs: nowEpochMs
            });
            this.#observer.observe(activity);
            if (this.#isVisible() && intersectsViewport(activity, this.#options.viewport)) {
                this.#intersecting.add(activity);
                this.#syncActivity(activity, nowEpochMs, displayMode);
            }
        }
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        this.#generation += 1;
        this.#cancelTimer();
        this.#observer.disconnect();
        this.#mutationObserver.disconnect();
        this.#registered.clear();
        this.#intersecting.clear();
        this.#tickerHealth.reset();
        (this.#options.documentRef ?? document).removeEventListener('visibilitychange', this.#visibilityListener);
    }

    #handleIntersections(entries: readonly IntersectionObserverEntry[], generation: number): void {
        if (!this.#isCurrent(generation) || !this.#isVisible()) {
            return;
        }
        const displayMode = this.#options.getDisplayMode();
        const nowEpochMs = this.#options.nowEpochMs();
        for (const entry of entries) {
            const activity = entry.target;
            if (!(activity instanceof HTMLElement) || !this.#registered.has(activity)) {
                continue;
            }
            if (!this.#owns(activity, displayMode)) {
                this.#unregister(activity);
                continue;
            }
            if (!entry.isIntersecting) {
                this.#intersecting.delete(activity);
                continue;
            }
            this.#intersecting.add(activity);
            this.#syncActivity(activity, nowEpochMs, displayMode);
        }
        this.#schedule();
    }

    #handleMutations(records: readonly MutationRecord[], generation: number): void {
        if (!this.#isCurrent(generation)) {
            return;
        }
        const impact = resolveActivityDurationMutationImpact(records);
        if (!impact.requiresPrune && impact.roots.size === 0) {
            this.#schedule();
            return;
        }
        const displayMode = this.#options.getDisplayMode();
        this.#prune(displayMode);
        for (const root of impact.roots) {
            this.#reconcile(root, this.#options.conversationId, displayMode);
        }
        this.#schedule();
    }

    #handleVisibilityChange(generation: number): void {
        if (!this.#isCurrent(generation)) {
            return;
        }
        if (!this.#isVisible()) {
            this.#cancelTimer();
            this.#resetHealth();
            return;
        }
        const displayMode = this.#options.getDisplayMode();
        this.#prune(displayMode);
        const nowEpochMs = this.#options.nowEpochMs();
        for (const activity of this.#registered.keys()) {
            if (intersectsViewport(activity, this.#options.viewport)) {
                this.#intersecting.add(activity);
                this.#syncActivity(activity, nowEpochMs, displayMode);
            } else {
                this.#intersecting.delete(activity);
            }
        }
        this.#schedule();
    }

    #handleTimer(generation: number): void {
        if (!this.#isCurrent(generation) || !this.#isVisible()) {
            return;
        }
        this.#timerId = null;
        this.#scheduledDueEpochMs = null;
        const monotonicMs = this.#options.nowMonotonicMs();
        if (this.#expectedDeadlineMs !== null) {
            this.#tickerHealth.record(monotonicMs, Math.max(0, monotonicMs - this.#expectedDeadlineMs));
        }
        this.#expectedDeadlineMs = null;
        const displayMode = this.#options.getDisplayMode();
        this.#prune(displayMode);
        const nowEpochMs = this.#options.nowEpochMs();
        for (const activity of this.#intersecting) {
            const registration = this.#registered.get(activity);
            if (registration && nowEpochMs >= registration.nextDueEpochMs) {
                this.#syncActivity(activity, nowEpochMs, displayMode);
            }
        }
        this.#schedule();
    }

    #syncActivity(activity: HTMLElement, nowEpochMs: number, displayMode: ChatActivityDurationDisplayMode): void {
        const registration = this.#registered.get(activity);
        if (!registration || !this.#registrationIsCurrent(activity, registration, displayMode)) {
            this.#unregister(activity);
            return;
        }
        if (registration.type === 'assistantHeader') {
            syncRunningAssistantHeaderDuration(activity, nowEpochMs);
        } else {
            syncRunningInlineActivityDuration(activity, nowEpochMs);
        }
        const elapsedMs = Math.max(0, nowEpochMs - registration.startedAtMs);
        const intervalMs = elapsedMs >= 60_000 ? WHOLE_SECOND_INTERVAL_MS : this.#tickerHealth.subMinuteIntervalMs;
        const remainderMs = elapsedMs % intervalMs;
        registration.nextDueEpochMs = nowEpochMs + (remainderMs === 0 ? intervalMs : intervalMs - remainderMs);
    }

    #schedule(): void {
        if (this.#disposed || !this.#isVisible()) {
            this.#cancelTimer();
            return;
        }
        let earliestDueEpochMs: number | null = null;
        for (const activity of this.#intersecting) {
            const nextDueEpochMs = this.#registered.get(activity)?.nextDueEpochMs ?? null;
            if (nextDueEpochMs !== null && (earliestDueEpochMs === null || nextDueEpochMs < earliestDueEpochMs)) {
                earliestDueEpochMs = nextDueEpochMs;
            }
        }
        if (earliestDueEpochMs === null) {
            this.#cancelTimer();
            this.#resetHealth();
            return;
        }
        if (this.#timerId !== null && this.#scheduledDueEpochMs === earliestDueEpochMs) {
            return;
        }
        this.#cancelTimer();
        const delayMs = Math.max(0, earliestDueEpochMs - this.#options.nowEpochMs());
        const generation = this.#generation;
        const expectedDeadlineMs = this.#options.nowMonotonicMs() + delayMs;
        const timerId = this.#options.setTimer(() => this.#handleTimer(generation), delayMs);
        this.#scheduledDueEpochMs = earliestDueEpochMs;
        this.#expectedDeadlineMs = expectedDeadlineMs;
        this.#timerId = timerId;
    }

    #cancelTimer(): void {
        if (this.#timerId !== null) {
            this.#options.clearTimer(this.#timerId);
        }
        this.#timerId = null;
        this.#scheduledDueEpochMs = null;
        this.#expectedDeadlineMs = null;
    }

    #prune(displayMode: ChatActivityDurationDisplayMode): void {
        for (const activity of Array.from(this.#registered.keys())) {
            if (this.#owns(activity, displayMode) && resolveStartedAtMs(activity) !== null) {
                continue;
            }
            this.#unregister(activity);
        }
    }

    #unregister(activity: HTMLElement): void {
        this.#observer.unobserve(activity);
        this.#registered.delete(activity);
        this.#intersecting.delete(activity);
    }

    #owns(activity: HTMLElement, displayMode: ChatActivityDurationDisplayMode): boolean {
        const conversationRoot = activity.closest('[data-current-conversation-id]');
        return activity.isConnected && this.#options.viewport.isConnected && this.#options.viewport.contains(activity) && conversationRoot instanceof HTMLElement && conversationRoot.getAttribute('data-current-conversation-id') === this.#options.conversationId && isRunningActivity(activity, displayMode);
    }

    #registrationIsCurrent(activity: HTMLElement, registration: RegisteredActivity, displayMode: ChatActivityDurationDisplayMode): boolean {
        const currentType = activity.matches(RUNNING_ASSISTANT_HEADER_SELECTOR) ? 'assistantHeader' : 'inline';
        return this.#owns(activity, displayMode) && registration.type === currentType && resolveStartedAtMs(activity) === registration.startedAtMs;
    }

    #isVisible(): boolean {
        return (this.#options.documentRef ?? document).visibilityState === 'visible';
    }

    #isCurrent(generation: number): boolean {
        return !this.#disposed && generation === this.#generation;
    }

    #resetHealth(): void {
        this.#tickerHealth.reset();
    }
}

export { ActivityDurationRuntime };
export type { ActivityDurationObserverFactory, ActivityDurationRuntimeOptions };
