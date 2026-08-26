/* SoAI - Dashboard page clock digital display widget [frontend/assets/ts/pages/dashboard/controllers/dashboardClockDigitalDisplayWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { applyTextContent } from '@core/dom/textContent.ts';
import type { DashboardHost, DashboardTimerControl } from '@core/edition/dashboardContribution.ts';

interface DashboardClockDigitalDisplayWidgetDependencies {
    host: DashboardHost;
    timers: DashboardTimerControl;
    isDestroyed: () => boolean;
}

type FlipCardUnit = 'hours' | 'minutes';

const CLOCK_FLIP_DURATION_MS = 460;
const formatClockDigits = (value: number): string => String(value).padStart(2, '0');

class DashboardClockDigitalDisplayWidget {
    readonly #host: DashboardHost;
    readonly #timers: DashboardTimerControl;
    readonly #isDestroyed: () => boolean;
    readonly #flipTimerIds: Record<FlipCardUnit, number | null> = { hours: null, minutes: null };

    constructor(dependencies: DashboardClockDigitalDisplayWidgetDependencies) {
        this.#host = dependencies.host;
        this.#timers = dependencies.timers;
        this.#isDestroyed = dependencies.isDestroyed;
    }

    buildFace(actionId: string): HTMLElement {
        const face = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-digital-face', 'data-action': actionId }), 'dashboard digital clock face');
        const board = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-flip-board' }), 'dashboard digital clock board');
        board.append(this.#buildCard('hours'), this.#buildCard('minutes'));
        face.appendChild(board);
        return face;
    }

    update(content: Element, now: Date): void {
        this.#updateCard(content, 'hours', formatClockDigits(now.getHours()));
        this.#updateCard(content, 'minutes', formatClockDigits(now.getMinutes()));
    }

    clearPendingAnimations(): void {
        this.#timers.clearTimer(this.#flipTimerIds['hours']);
        this.#timers.clearTimer(this.#flipTimerIds['minutes']);
        this.#flipTimerIds['hours'] = null;
        this.#flipTimerIds['minutes'] = null;
    }

    #buildCard(unit: FlipCardUnit): HTMLElement {
        const card = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-clock-flip-card', dataset: { clockFlipCard: unit } }), `dashboard digital ${unit} card`);
        card.append(this.#buildLayer('dashboard-clock-flip-half dashboard-clock-flip-current-top'), this.#buildLayer('dashboard-clock-flip-half dashboard-clock-flip-current-bottom'), this.#buildLayer('dashboard-clock-flip-half dashboard-clock-flip-overlay-top'), this.#buildLayer('dashboard-clock-flip-half dashboard-clock-flip-overlay-bottom'));
        return card;
    }

    #buildLayer(className: string): HTMLElement {
        const layer = narrowHTMLElement(this.#host.createElement('div', { className }), 'dashboard digital clock layer');
        layer.appendChild(narrowHTMLElement(this.#host.createElement('span', { className: 'dashboard-clock-flip-text' }, '00'), 'dashboard digital clock text'));
        return layer;
    }

    #updateCard(content: Element, unit: FlipCardUnit, nextValue: string): void {
        const card = this.#host.optionalHTMLElement(`[data-clock-flip-card='${unit}']`, content);
        if (!card) {
            return;
        }
        const currentValue = card.dataset['clockValue'];
        if (!currentValue) {
            this.#fillCard(card, nextValue);
            return;
        }
        if (currentValue === nextValue) {
            return;
        }
        card.dataset['clockValue'] = nextValue;
        this.#setLayerText(card, '.dashboard-clock-flip-current-top', currentValue);
        this.#setLayerText(card, '.dashboard-clock-flip-current-bottom', currentValue);
        this.#setLayerText(card, '.dashboard-clock-flip-overlay-top', currentValue);
        this.#setLayerText(card, '.dashboard-clock-flip-overlay-bottom', nextValue);
        this.#timers.clearTimer(this.#flipTimerIds[unit]);
        this.#flipTimerIds[unit] = null;
        card.classList.remove('dashboard-clock-flip-card-flipping');
        void card.offsetWidth;
        card.classList.add('dashboard-clock-flip-card-flipping');
        this.#flipTimerIds[unit] = this.#timers.setTimer((): void => {
            this.#flipTimerIds[unit] = null;
            if (this.#isDestroyed() || !card.isConnected) {
                return;
            }
            card.classList.remove('dashboard-clock-flip-card-flipping');
            this.#fillCard(card, nextValue);
        }, CLOCK_FLIP_DURATION_MS);
    }

    #fillCard(card: HTMLElement, value: string): void {
        card.dataset['clockValue'] = value;
        this.#resolveCardTextLayers(card).forEach((layer) => {
            applyTextContent(layer, value);
        });
    }

    #setLayerText(card: HTMLElement, selector: string, value: string): void {
        const layer = this.#host.optionalHTMLElement(selector, card);
        if (layer) {
            const text = this.#host.optionalHTMLElement('.dashboard-clock-flip-text', layer);
            if (text) {
                applyTextContent(text, value);
            }
        }
    }

    #resolveCardTextLayers(card: HTMLElement): HTMLElement[] {
        const layers: HTMLElement[] = [];
        for (const child of Array.from(card.children)) {
            if (!(child instanceof HTMLElement)) {
                continue;
            }
            const textNode = child.firstElementChild;
            if (!(textNode instanceof HTMLElement)) {
                throw new Error('Dashboard digital clock card layers must contain text nodes');
            }
            layers.push(textNode);
        }
        return layers;
    }
}

export { DashboardClockDigitalDisplayWidget };
export type { DashboardClockDigitalDisplayWidgetDependencies };
