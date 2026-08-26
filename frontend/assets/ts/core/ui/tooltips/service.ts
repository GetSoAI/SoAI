/* SoAI - Shared UI tooltips service [frontend/assets/ts/core/ui/tooltips/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { bindTooltipServiceEvents } from '@core/ui/tooltips/tooltipEventBindings.ts';
import { positionTooltipElement } from '@core/ui/tooltips/tooltipPositioning.ts';

type TooltipService = {
    initialize: () => void;
    teardown: () => void;
};

const TOOLTIP_ATTRIBUTE = 'data-tooltip';
const TOOLTIP_VISIBLE_CLASS = 'is-visible';
const TOOLTIP_SHOW_DELAY_MS = 1200;

const readTooltipText = (target: Element): string => {
    const raw = target.getAttribute(TOOLTIP_ATTRIBUTE);
    const normalized = typeof raw === 'string' ? raw.trim() : '';
    return normalized;
};

class TooltipServiceImpl implements TooltipService {
    #initialized = false;
    #resources = new ResourceTracker();
    #tooltipElement: HTMLDivElement | null = null;
    #activeTarget: Element | null = null;
    #pendingTarget: Element | null = null;
    #pendingTimerId: number | null = null;
    #isKeyboardModality = false;

    initialize(): void {
        if (this.#initialized) {
            return;
        }
        this.#initialized = true;

        const documentRef = dom.getDocument();
        const body = dom.getBody();
        const view = documentRef.defaultView;

        const tooltipElement = documentRef.createElement('div');
        tooltipElement.className = 'ui-tooltip';
        tooltipElement.setAttribute('role', 'tooltip');
        tooltipElement.setAttribute('aria-hidden', 'true');
        body.appendChild(tooltipElement);

        this.#tooltipElement = tooltipElement;
        bindTooltipServiceEvents({
            documentRef,
            view,
            resources: this.#resources,
            attributeName: TOOLTIP_ATTRIBUTE,
            shouldShowOnFocus: (target) => this.#shouldShowTooltipOnFocus(target),
            handleEnter: (target) => this.#handleEnter(target),
            handleLeave: (target, relatedCandidate) => this.#handleLeave(target, relatedCandidate),
            handleAttributeChanged: (target) => this.#handleTooltipAttributeChanged(target),
            handleResize: () => this.#repositionActiveTooltip(),
            hide: () => this.hide(),
            setKeyboardModality: (isKeyboardModality) => {
                this.#isKeyboardModality = isKeyboardModality;
            }
        });
    }

    hide(): void {
        this.#clearPending();
        const tooltipElement = this.#tooltipElement;
        if (!tooltipElement) {
            return;
        }
        this.#activeTarget = null;
        tooltipElement.classList.remove(TOOLTIP_VISIBLE_CLASS);
        tooltipElement.setAttribute('aria-hidden', 'true');
    }

    teardown(): void {
        this.hide();
        this.#resources.cleanup();
        const tooltipElement = this.#tooltipElement;
        if (tooltipElement) {
            tooltipElement.remove();
        }
        this.#tooltipElement = null;
        this.#activeTarget = null;
        this.#initialized = false;
    }

    #shouldShowTooltipOnFocus(target: Element): boolean {
        if (!(target instanceof HTMLElement)) {
            return false;
        }
        return this.#isKeyboardModality;
    }

    #handleEnter(target: Element): void {
        if (this.#activeTarget === target) {
            return;
        }
        const text = readTooltipText(target);
        if (!text) {
            return;
        }
        if (this.#activeTarget) {
            this.#show(target, text);
            return;
        }
        this.#scheduleShow(target);
    }

    #handleLeave(leavingTarget: Element, relatedCandidate: EventTarget | null): void {
        if (relatedCandidate instanceof Node && leavingTarget.contains(relatedCandidate)) {
            return;
        }
        if (this.#activeTarget === leavingTarget) {
            this.hide();
            return;
        }
        if (this.#pendingTarget === leavingTarget) {
            this.#clearPending();
        }
    }

    #handleTooltipAttributeChanged(target: Element): void {
        if (target !== this.#activeTarget && target !== this.#pendingTarget) {
            return;
        }
        const text = readTooltipText(target);
        if (!text) {
            this.hide();
            return;
        }
        if (target === this.#activeTarget) {
            this.#show(target, text);
        }
    }

    #repositionActiveTooltip(): void {
        const active = this.#activeTarget;
        const tooltipElement = this.#tooltipElement;
        if (!active || !tooltipElement) {
            return;
        }
        const text = readTooltipText(active);
        if (!text) {
            this.hide();
            return;
        }
        positionTooltipElement({ target: active, tooltipElement });
    }

    #show(target: Element, text: string): void {
        this.#clearPending();
        const tooltipElement = this.#tooltipElement;
        if (!tooltipElement) {
            return;
        }
        this.#activeTarget = target;
        tooltipElement.textContent = text;
        positionTooltipElement({ target, tooltipElement });
        tooltipElement.classList.add(TOOLTIP_VISIBLE_CLASS);
        tooltipElement.setAttribute('aria-hidden', 'false');
    }

    #scheduleShow(target: Element): void {
        this.#clearPending();
        const tooltipElement = this.#tooltipElement;
        const view = target.ownerDocument.defaultView;
        if (!tooltipElement || !view) {
            return;
        }
        this.#pendingTarget = target;
        this.#pendingTimerId = view.setTimeout(() => {
            const pendingTarget = this.#pendingTarget;
            if (!pendingTarget || pendingTarget !== target) {
                return;
            }
            const latestText = readTooltipText(target);
            if (!latestText) {
                this.hide();
                return;
            }
            this.#show(target, latestText);
        }, TOOLTIP_SHOW_DELAY_MS);
    }

    #clearPending(): void {
        const activeTimerId = this.#pendingTimerId;
        const target = this.#pendingTarget;
        if (activeTimerId === null || !target) {
            this.#pendingTimerId = null;
            this.#pendingTarget = null;
            return;
        }
        const view = target.ownerDocument.defaultView;
        if (view) {
            view.clearTimeout(activeTimerId);
        }
        this.#pendingTimerId = null;
        this.#pendingTarget = null;
    }
}

const createTooltipService = (): TooltipService => new TooltipServiceImpl();

export { createTooltipService };
export type { TooltipService };
