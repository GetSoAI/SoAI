/* SoAI - Shared page outlet visual transaction [frontend/assets/ts/core/pageoutlet/visualTransaction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { PAGE_CONTENT_READY, PAGE_TRANSITIONING_IN, PAGE_TRANSITION_MODE_ATTRIBUTE, isReduceMotionsEnabled, resolveActiveSection, requirePageTransitionSurface, waitForElementAnimations } from '@core/pageTransitions.ts';
import { DelayedPageOutletLoading } from '@core/pageoutlet/delayedLoading.ts';
import { startPageExitAnimation, captureExitAnimationStartState } from '@core/pageoutlet/exitAnimation.ts';

interface PageOutletVisualTransactionOptions {
    resources: ResourceTracker;
    setReady(): void;
    showLoading(label: string | null, detail: string | null, delayed: boolean): void;
}

class PageOutletVisualTransaction {
    #container: HTMLElement | null = null;
    #activeToken: symbol | null = null;
    #exitingSection: Element | null = null;
    #exitEpoch: symbol | null = null;
    #exitTask: Promise<void> | null = null;
    #exitAnimation: Animation | null = null;
    #delayedLoading: DelayedPageOutletLoading;
    #setReady: () => void;

    constructor(options: PageOutletVisualTransactionOptions) {
        this.#setReady = options.setReady;
        this.#delayedLoading = new DelayedPageOutletLoading({
            resources: options.resources,
            showLoading: options.showLoading
        });
    }

    setContainer(container: HTMLElement): void {
        this.cancel();
        this.#container = container;
    }

    begin(): symbol {
        this.supersede();
        const token = Symbol('page-visual-transaction');
        this.#activeToken = token;
        return token;
    }

    supersede(token: symbol | null = null): void {
        if (token !== null && this.#activeToken !== token) {
            return;
        }
        this.#activeToken = null;
        this.#delayedLoading.cancel();
        this.#adoptHiddenMountedSection();
    }

    showPreparationLoading(token: symbol): void {
        if (this.#activeToken === token) this.#delayedLoading.schedule();
    }

    async preparePageExit(token: symbol): Promise<void> {
        if (this.#activeToken !== token) {
            return;
        }
        const section = resolveActiveSection(this.#requireContainer());
        if (!section) {
            return;
        }
        const pending = this.#exitingSection === section ? this.#exitTask : null;
        if (pending) {
            await pending;
            return;
        }
        const epoch = Symbol('page-exit');
        this.#exitingSection = section;
        this.#exitEpoch = epoch;
        const task = this.#runPageExit(section, epoch);
        this.#exitTask = task;
        try {
            await task;
        } catch (error) {
            if (this.#exitTask === task) {
                this.#exitTask = null;
            }
            if (this.#activeToken !== token) {
                return;
            }
            throw ensureError(error);
        }
    }

    commit(token: symbol): void {
        if (this.#activeToken !== token) {
            return;
        }
        this.#activeToken = null;
        this.#clearExitState();
        this.#delayedLoading.cancel();
        this.#setReady();
    }

    async revealEnteredPage(token: symbol): Promise<void> {
        if (this.#activeToken !== token) {
            return;
        }
        const container = this.#requireContainer();
        const section = resolveActiveSection(container);
        if (!section) {
            throw new Error('Page enter animation requires a mounted page section');
        }
        this.#clearExitState();
        section.classList.remove(PAGE_CONTENT_READY, PAGE_TRANSITIONING_IN);
        const transitionSurface = requirePageTransitionSurface(section);
        if (transitionSurface.mode === 'surface') {
            section.setAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE, 'surface');
        } else {
            section.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
        }
        this.#delayedLoading.cancel();
        this.#setReady();
        if (isReduceMotionsEnabled()) {
            section.classList.add(PAGE_CONTENT_READY);
            section.classList.remove(PAGE_TRANSITIONING_IN);
            section.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
            return;
        }
        section.classList.add(PAGE_TRANSITIONING_IN);
        await this.#waitForFrame();
        if (this.#activeToken !== token) {
            return;
        }
        section.classList.add(PAGE_CONTENT_READY);
        try {
            await waitForElementAnimations(transitionSurface.surface, { requireAnimation: true });
        } catch (error) {
            if (this.#activeToken !== token) {
                return;
            }
            throw ensureError(error);
        }
        if (this.#activeToken !== token) {
            return;
        }
        section.classList.remove(PAGE_TRANSITIONING_IN);
        section.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
    }

    completeRevealAfterFailure(token: symbol): void {
        if (this.#activeToken !== token) return;
        const section = resolveActiveSection(this.#requireContainer());
        if (!section) throw new Error('Page reveal recovery requires a mounted page section');
        this.#clearExitState();
        section.classList.add(PAGE_CONTENT_READY);
        section.classList.remove(PAGE_TRANSITIONING_IN);
        section.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
    }

    fail(token: symbol): void {
        if (this.#activeToken !== token) {
            return;
        }
        this.#activeToken = null;
        this.#restoreExitingSection();
        this.#delayedLoading.cancel();
    }

    cancel(token: symbol | null = null): void {
        if (token !== null && this.#activeToken !== token) {
            return;
        }
        this.#activeToken = null;
        this.#restoreExitingSection();
        this.#delayedLoading.cancel();
        this.#setReady();
    }

    async #waitForFrame(): Promise<void> {
        const frame = getRequestAnimationFrame();
        await new Promise<void>((resolve) => frame(() => resolve()));
    }

    #requireContainer(): HTMLElement {
        if (!this.#container) {
            throw new Error('PageOutlet visual transaction requires a container');
        }
        return this.#container;
    }

    async #runPageExit(section: Element, epoch: symbol): Promise<void> {
        if (isReduceMotionsEnabled()) {
            this.#applyExitedSectionState(section, epoch);
            return;
        }
        const animation = startPageExitAnimation(section, captureExitAnimationStartState(section));
        this.#exitAnimation = animation;
        try {
            await animation.finished;
        } catch (error) {
            if (this.#exitEpoch !== epoch) {
                return;
            }
            throw ensureError(error);
        } finally {
            if (this.#exitAnimation === animation) {
                this.#exitAnimation = null;
            }
            animation.cancel();
        }
        this.#applyExitedSectionState(section, epoch);
    }

    #applyExitedSectionState(section: Element, epoch: symbol): void {
        if (this.#exitEpoch !== epoch) {
            return;
        }
        section.classList.remove(PAGE_CONTENT_READY, PAGE_TRANSITIONING_IN);
    }

    #clearExitState(): void {
        this.#exitingSection = null;
        this.#exitEpoch = null;
        this.#exitTask = null;
        this.#exitAnimation = null;
    }

    #revealMountedSection(): void {
        const mounted = this.#container ? resolveActiveSection(this.#container) : null;
        if (!mounted || mounted === this.#exitingSection) {
            return;
        }
        this.#revealSection(mounted);
    }

    #adoptHiddenMountedSection(): void {
        const mounted = this.#container ? resolveActiveSection(this.#container) : null;
        if (!mounted || mounted === this.#exitingSection) return;
        if (mounted.classList.contains(PAGE_CONTENT_READY) && !mounted.classList.contains(PAGE_TRANSITIONING_IN)) return;
        this.#exitAnimation?.cancel();
        this.#clearExitState();
        this.#exitingSection = mounted;
        this.#exitEpoch = Symbol('page-exit-superseded');
        this.#exitTask = Promise.resolve();
        mounted.classList.remove(PAGE_CONTENT_READY, PAGE_TRANSITIONING_IN);
        mounted.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
    }

    #revealSection(section: Element): void {
        section.classList.add(PAGE_CONTENT_READY);
        section.classList.remove(PAGE_TRANSITIONING_IN);
        section.removeAttribute(PAGE_TRANSITION_MODE_ATTRIBUTE);
    }

    #restoreExitingSection(): void {
        const section = this.#exitingSection;
        this.#exitAnimation?.cancel();
        this.#clearExitState();
        if (section) {
            this.#revealSection(section);
        }
        this.#revealMountedSection();
    }
}

export { PageOutletVisualTransaction };
