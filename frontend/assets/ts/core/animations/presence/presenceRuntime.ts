/* SoAI - Presence motion runtime observing control visibility changes [frontend/assets/ts/core/animations/presence/presenceRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isLayoutParentRendered, isRendered, readComputedStyle } from '@core/animations/presence/presenceGeometry.ts';
import { animatePresenceMorph, finishPresenceAnimations, isPresenceAnimating, isPresenceMorphing, measurePresenceSize, stopPresenceAnimation, type PresenceSize } from '@core/animations/presence/presenceMotion.ts';
import { consumeCompletedHiddenExit, consumePresenceEnterRequest, exitWithPresence, isPresenceExiting, prepareEnterWithPresence } from '@core/animations/presence/presenceTransitions.ts';
import { canAnimatePresence, recordModalPresenceInteraction, resetModalPresence } from '@core/animations/presence/presenceEligibility.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { dom } from '@core/dom/dom.ts';
const PRESENCE_TARGET_SELECTOR = "button, [role='button'], [data-presence]";
const PRESENCE_MORPH_SELECTOR = '[data-presence-morph]';
const HIDDEN_ATTRIBUTE = 'hidden';
const PRESENCE_STATE_ATTRIBUTES = new Set(['class', 'style', HIDDEN_ATTRIBUTE, 'disabled', 'tabindex', 'aria-pressed', 'aria-checked', 'aria-selected', 'aria-expanded', 'aria-disabled', 'aria-busy', 'aria-current']);

interface PresenceVisibilityChange {
    classHidden: boolean | null;
    attributeHidden: boolean | null;
}

interface PresenceRuntimeService {
    initialize: () => void;
    dispose: () => void;
}

const hasHiddenClassToken = (classValue: string | null): boolean => (classValue ?? '').split(/\s+/u).includes(CSS_CLASSES.HIDDEN);

const isVisibilityHidden = (element: Element): boolean => element.classList.contains(CSS_CLASSES.HIDDEN) || element.hasAttribute(HIDDEN_ATTRIBUTE);

const wasVisibilityHidden = (element: Element, change: PresenceVisibilityChange): boolean => (change.classHidden ?? element.classList.contains(CSS_CLASSES.HIDDEN)) || (change.attributeHidden ?? element.hasAttribute(HIDDEN_ATTRIBUTE));

const isPresenceTarget = (element: HTMLElement): boolean => element.matches(PRESENCE_TARGET_SELECTOR);

const collectPresenceTargets = (node: HTMLElement): HTMLElement[] => [node, ...dom.resolveAll(PRESENCE_TARGET_SELECTOR, node)].filter((target): target is HTMLElement => target instanceof HTMLElement && isPresenceTarget(target));

const readPresenceIdentity = (element: HTMLElement): string => {
    const attributes = Array.from(element.attributes)
        .filter((attribute) => !PRESENCE_STATE_ATTRIBUTES.has(attribute.name))
        .map((attribute) => `${attribute.name}=${attribute.value}`)
        .sort((first, second) => first.localeCompare(second, 'en'));
    const text = attributes.some((entry) => !entry.startsWith('type=')) ? '' : (element.textContent ?? '').trim();
    return `${element.tagName}|${attributes.join('|')}|${text}`;
};

const collectReplacedIdentities = (records: MutationRecord[]): Map<Node, Map<string, number>> => {
    const replaced = new Map<Node, Map<string, number>>();
    records.forEach((record) => {
        if (record.type !== 'childList') return;
        record.removedNodes.forEach((node) => {
            if (!(node instanceof HTMLElement)) return;
            const identities = replaced.get(record.target) ?? new Map<string, number>();
            collectPresenceTargets(node).forEach((target) => {
                const identity = readPresenceIdentity(target);
                identities.set(identity, (identities.get(identity) ?? 0) + 1);
            });
            replaced.set(record.target, identities);
        });
    });
    return replaced;
};

const consumeReplacedIdentity = (identities: Map<string, number> | undefined, target: HTMLElement): boolean => {
    if (identities === undefined || identities.size === 0) return false;
    const identity = readPresenceIdentity(target);
    const count = identities.get(identity) ?? 0;
    if (count <= 0) return false;
    identities.set(identity, count - 1);
    return true;
};

class PresenceRuntime implements PresenceRuntimeService {
    readonly #documentRef: Document;
    #visibilityObserver: MutationObserver | null = null;
    #morphObserver: MutationObserver | null = null;
    #morphSizeObserver: ResizeObserver | null = null;
    #knownTargets = new WeakSet<Element>();
    #knownMorphTargets = new Set<HTMLElement>();
    readonly #morphSizes = new WeakMap<Element, PresenceSize>();

    constructor(documentRef: Document) {
        this.#documentRef = documentRef;
    }

    initialize(): void {
        const view = this.#documentRef.defaultView;
        if (this.#visibilityObserver || !view) {
            return;
        }
        dom.resolveAll(PRESENCE_TARGET_SELECTOR, this.#documentRef).forEach((target) => this.#knownTargets.add(target));
        this.#visibilityObserver = new view.MutationObserver(this.#handleVisibilityRecords);
        this.#visibilityObserver.observe(this.#documentRef.body, { subtree: true, childList: true, attributes: true, attributeOldValue: true, attributeFilter: ['class', HIDDEN_ATTRIBUTE] });
        this.#observeMorphTargets(view);
        this.#documentRef.addEventListener('visibilitychange', this.#handleDocumentVisibility);
        this.#documentRef.addEventListener('core.modal.open', this.#handleModalSession);
        this.#documentRef.addEventListener('core.modal.close', this.#handleModalSession);
        for (const type of ['pointerdown', 'keydown', 'click']) {
            this.#documentRef.addEventListener(type, recordModalPresenceInteraction, true);
        }
    }

    dispose(): void {
        finishPresenceAnimations(this.#documentRef);
        this.#documentRef.removeEventListener('visibilitychange', this.#handleDocumentVisibility);
        this.#documentRef.removeEventListener('core.modal.open', this.#handleModalSession);
        this.#documentRef.removeEventListener('core.modal.close', this.#handleModalSession);
        for (const type of ['pointerdown', 'keydown', 'click']) {
            this.#documentRef.removeEventListener(type, recordModalPresenceInteraction, true);
        }
        this.#visibilityObserver?.disconnect();
        this.#morphObserver?.disconnect();
        this.#morphSizeObserver?.disconnect();
        this.#visibilityObserver = null;
        this.#morphObserver = null;
        this.#morphSizeObserver = null;
        this.#knownTargets = new WeakSet<Element>();
        this.#knownMorphTargets = new Set<HTMLElement>();
    }

    #handleModalSession = (event: Event): void => {
        if (event.target instanceof Element) {
            resetModalPresence(event.target);
            for (const child of event.target.children) finishPresenceAnimations(child);
        }
    };

    #handleDocumentVisibility = (): void => {
        if (this.#documentRef.visibilityState !== 'visible') {
            finishPresenceAnimations(this.#documentRef);
        }
    };

    #handleVisibilityRecords = (records: MutationRecord[]): void => {
        const retainedMorphRecords = records.some((record) => record.type === 'childList' && Array.from(record.removedNodes).some((node) => node instanceof HTMLElement)) ? this.#releaseDetachedMorphTargets() : [];
        const changes = new Map<HTMLElement, PresenceVisibilityChange>();
        const pending = new Map<HTMLElement, { hidden: boolean; visualOnly: boolean; animate: boolean }>();
        const replacedIdentities = collectReplacedIdentities(records);
        records.forEach((record) => {
            if (record.type === 'childList') {
                record.addedNodes.forEach((node, index) => {
                    if (!(node instanceof HTMLElement)) {
                        return;
                    }
                    this.#registerMorphTargets(node);
                    const unchangedReplacement = record.removedNodes[index]?.isEqualNode(node) === true;
                    const requested = consumePresenceEnterRequest(node);
                    if (requested !== undefined && !isPresenceExiting(node)) {
                        pending.set(node, { hidden: false, visualOnly: false, animate: requested });
                    }
                    collectPresenceTargets(node).forEach((target) => {
                        if (this.#knownTargets.has(target)) {
                            return;
                        }
                        this.#knownTargets.add(target);
                        const rerendered = consumeReplacedIdentity(replacedIdentities.get(record.target), target);
                        if (!unchangedReplacement && !rerendered && !isPresenceExiting(target) && (requested === undefined || target !== node)) {
                            pending.set(target, { hidden: false, visualOnly: target !== node, animate: true });
                        }
                    });
                });
                return;
            }
            if (!(record.target instanceof HTMLElement)) {
                return;
            }
            const change = changes.get(record.target) ?? { classHidden: null, attributeHidden: null };
            if (record.attributeName === HIDDEN_ATTRIBUTE) {
                change.attributeHidden ??= record.oldValue !== null;
            } else {
                change.classHidden ??= hasHiddenClassToken(record.oldValue);
            }
            changes.set(record.target, change);
        });
        changes.forEach((change, element) => {
            const hidden = isVisibilityHidden(element);
            if (hidden === wasVisibilityHidden(element, change)) {
                return;
            }
            if (isPresenceTarget(element)) {
                if (!hidden && isPresenceExiting(element)) {
                    consumePresenceEnterRequest(element);
                    return;
                }
                pending.set(element, { hidden, visualOnly: false, animate: pending.get(element)?.animate ?? (!hidden ? consumePresenceEnterRequest(element) : undefined) ?? true });
            }
        });
        const transitions = Array.from(pending, ([element, state]) => {
            let depth = 0;
            for (let parent = element.parentElement; parent; parent = parent.parentElement) depth += 1;
            return { element, depth, ...state };
        });
        transitions.sort((first, second) => first.depth - second.depth);
        const enters: Array<() => void> = [];
        transitions.forEach(({ element, hidden, visualOnly, animate }) => {
            if (!element.isConnected || (!hidden && isVisibilityHidden(element))) {
                return;
            }
            if (hidden) {
                this.#exit(element);
                return;
            }
            for (let parent = element.parentElement; parent; parent = parent.parentElement) {
                if (pending.get(parent)?.hidden === false) return;
            }
            const canAnimate = animate && this.#documentRef.visibilityState === 'visible' && canAnimatePresence(element) && isRendered(element);
            enters.push(prepareEnterWithPresence(element, canAnimate, visualOnly));
        });
        enters.forEach((start) => start());
        if (retainedMorphRecords.length > 0) this.#handleMorphRecords(retainedMorphRecords);
    };

    #exit(element: HTMLElement): void {
        if (consumeCompletedHiddenExit(element)) return;
        if (isPresenceExiting(element)) {
            return;
        }
        const heldDisplay = this.#documentRef.visibilityState === 'visible' && canAnimatePresence(element) ? this.#readShownDisplay(element) : null;
        if (!heldDisplay) {
            stopPresenceAnimation(element);
            return;
        }
        exitWithPresence(element, heldDisplay, null);
    }
    #readShownDisplay(element: HTMLElement): string | null {
        const hadHiddenClass = element.classList.contains(CSS_CLASSES.HIDDEN);
        const hiddenAttributeValue = element.getAttribute(HIDDEN_ATTRIBUTE);
        element.classList.remove(CSS_CLASSES.HIDDEN);
        element.removeAttribute(HIDDEN_ATTRIBUTE);
        const display = isLayoutParentRendered(element) ? (readComputedStyle(element)?.display ?? 'none') : 'none';
        if (hadHiddenClass) {
            element.classList.add(CSS_CLASSES.HIDDEN);
        }
        if (hiddenAttributeValue !== null) {
            element.setAttribute(HIDDEN_ATTRIBUTE, hiddenAttributeValue);
        }
        this.#visibilityObserver?.takeRecords();
        return display === 'none' ? null : display;
    }

    #observeMorphTargets(view: Window & typeof globalThis): void {
        const targets = dom.resolveAll(PRESENCE_MORPH_SELECTOR, this.#documentRef).filter((target): target is HTMLElement => target instanceof HTMLElement);
        if (typeof view.ResizeObserver !== 'function') {
            return;
        }
        this.#morphObserver = new view.MutationObserver(this.#handleMorphRecords);
        this.#morphSizeObserver = new view.ResizeObserver(this.#handleMorphResize);
        targets.forEach((target) => this.#registerMorphTarget(target));
    }

    #registerMorphTargets(node: HTMLElement): void {
        const targets = [node, ...dom.resolveAll(PRESENCE_MORPH_SELECTOR, node)].filter((target): target is HTMLElement => target instanceof HTMLElement && target.matches(PRESENCE_MORPH_SELECTOR));
        targets.forEach((target) => this.#registerMorphTarget(target));
    }

    #registerMorphTarget(target: HTMLElement): void {
        if (!target.isConnected || this.#knownMorphTargets.has(target) || !this.#morphObserver || !this.#morphSizeObserver) {
            return;
        }
        this.#knownMorphTargets.add(target);
        this.#morphObserver.observe(target, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
        this.#morphSizeObserver.observe(target);
        this.#recordMorphSize(target);
    }

    #releaseDetachedMorphTargets(): MutationRecord[] {
        const detached = Array.from(this.#knownMorphTargets).filter((target) => !target.isConnected);
        if (detached.length === 0 || !this.#morphObserver) return [];
        const retained = this.#morphObserver.takeRecords().filter((record) => record.target.isConnected);
        this.#morphObserver.disconnect();
        for (const target of detached) {
            this.#morphSizeObserver?.unobserve(target);
            this.#knownMorphTargets.delete(target);
            this.#morphSizes.delete(target);
        }
        for (const target of this.#knownMorphTargets) this.#morphObserver.observe(target, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
        return retained;
    }

    #recordMorphSize(target: HTMLElement): PresenceSize | null {
        const size = measurePresenceSize(target);
        if (size) {
            this.#morphSizes.set(target, size);
        } else {
            this.#morphSizes.delete(target);
        }
        return size;
    }
    #handleMorphRecords = (records: MutationRecord[]): void => {
        const targets = new Set<HTMLElement>();
        records.forEach((record) => {
            const target = record.target instanceof Element ? record.target : record.target.parentElement;
            const morphTarget = target?.closest(PRESENCE_MORPH_SELECTOR);
            if (morphTarget instanceof HTMLElement) {
                targets.add(morphTarget);
            }
        });
        targets.forEach((target) => {
            if (isPresenceAnimating(target) && !isPresenceMorphing(target)) {
                return;
            }
            const previous = isPresenceAnimating(target) ? measurePresenceSize(target) : this.#morphSizes.get(target);
            stopPresenceAnimation(target);
            const next = this.#recordMorphSize(target);
            if (previous && next && this.#documentRef.visibilityState === 'visible') {
                animatePresenceMorph(target, previous, next);
            }
        });
    };
    #handleMorphResize = (entries: ResizeObserverEntry[]): void => {
        entries.forEach((entry) => {
            if (entry.target instanceof HTMLElement && this.#knownMorphTargets.has(entry.target) && !isPresenceAnimating(entry.target)) {
                this.#recordMorphSize(entry.target);
            }
        });
    };
}

const createPresenceRuntime = (documentRef: Document): PresenceRuntimeService => new PresenceRuntime(documentRef);

export { createPresenceRuntime };
export type { PresenceRuntimeService };
