/* SoAI - Charts feature chart filters events [frontend/assets/ts/features/charts/chartfilters/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { FILTER_ICON_NAMES, resolveIconMarkup } from '@features/charts/chartfilters/constants.ts';
import { buildCompactSummaryText } from '@features/charts/chartfilters/dom.ts';
import type { ChartFiltersElements, ChartFiltersState, FilterType, InternalChartFiltersConfig } from '@features/charts/chartfilters/types.ts';

interface ChartFiltersCompactModeContext {
    container: HTMLElement;
    state: ChartFiltersState;
    config: InternalChartFiltersConfig;
    elements: ChartFiltersElements;
    resources: ResourceTracker;
    getFilterLabel: (type: FilterType) => string;
    formatTimeRange: (minutes: number) => string;
}

interface ChartFiltersCompactModeState {
    triggerClickDisposer: (() => void) | null;
    compactChangeDisposer: (() => void) | null;
    outsideClickDisposer: (() => void) | null;
    compactOutsideClickHandler: ((event: Event) => void) | null;
}

interface ChartFiltersFullscreenContext {
    container: HTMLElement;
    fullscreenTarget: string | Element | null;
    button: HTMLButtonElement | null;
}

const createCompactModeState = (): ChartFiltersCompactModeState => ({
    triggerClickDisposer: null,
    compactChangeDisposer: null,
    outsideClickDisposer: null,
    compactOutsideClickHandler: null
});

const updateCompactSummary = (context: ChartFiltersCompactModeContext): void => {
    if (!context.elements.compactTrigger) {
        return;
    }
    const summaryHost = dom.resolve('.chart-filters-trigger-summary', context.elements.compactTrigger);
    const summaryText = buildCompactSummaryText({
        state: context.state,
        config: {
            showChartType: context.config.showChartType,
            showCategory: context.config.showCategory,
            showTimeRange: context.config.showTimeRange
        },
        categories: context.config.categories,
        formatTimeRange: context.formatTimeRange
    });
    if (summaryHost instanceof HTMLElement) {
        summaryHost.textContent = summaryText;
    }
};

const closeCompactPanel = (context: ChartFiltersCompactModeContext, state: ChartFiltersCompactModeState): void => {
    if (state.outsideClickDisposer) {
        state.outsideClickDisposer();
        state.outsideClickDisposer = null;
    }
    state.compactOutsideClickHandler = null;
    context.elements.compactPanel?.setAttribute('data-open', 'false');
    context.elements.compactTrigger?.setAttribute('aria-expanded', 'false');
    context.container.dataset['filtersPanelOpen'] = 'false';
};

const bindCompactOutsideClick = (context: ChartFiltersCompactModeContext, state: ChartFiltersCompactModeState): void => {
    if (state.outsideClickDisposer) {
        state.outsideClickDisposer();
        state.outsideClickDisposer = null;
    }
    const closePanel = (): void => {
        if (!context.elements.compactPanel || !context.elements.compactTrigger) {
            closeCompactPanel(context, state);
            return;
        }
        const activeElement = context.container.ownerDocument.activeElement;
        if ((activeElement !== null && context.elements.compactPanel.contains(activeElement)) || (activeElement !== null && context.elements.compactTrigger.contains(activeElement))) {
            return;
        }
        closeCompactPanel(context, state);
    };
    state.compactOutsideClickHandler = (event: Event): void => {
        const target = event.target instanceof Node ? event.target : null;
        if (!target) return;
        if (context.elements.compactPanel?.contains(target) || context.elements.compactTrigger?.contains(target)) {
            return;
        }
        closePanel();
    };
    const handler = state.compactOutsideClickHandler;
    context.resources.setTimeout(() => {
        if (!handler || state.compactOutsideClickHandler !== handler) {
            return;
        }
        state.outsideClickDisposer = context.resources.addEventListener(dom.getDocument(), 'click', handler);
    }, 0);
};

const openCompactPanel = (context: ChartFiltersCompactModeContext, state: ChartFiltersCompactModeState): void => {
    bindCompactOutsideClick(context, state);
};

const toggleCompactPanel = (context: ChartFiltersCompactModeContext, state: ChartFiltersCompactModeState): void => {
    const isOpen = context.container.dataset['filtersPanelOpen'] === 'true';
    const nextState = !isOpen;
    context.container.dataset['filtersPanelOpen'] = String(nextState);
    context.elements.compactTrigger?.setAttribute('aria-expanded', String(nextState));
    if (nextState) {
        openCompactPanel(context, state);
        return;
    }
    closeCompactPanel(context, state);
};

const bindCompactTrigger = (context: ChartFiltersCompactModeContext, state: ChartFiltersCompactModeState): void => {
    if (state.triggerClickDisposer) {
        state.triggerClickDisposer();
        state.triggerClickDisposer = null;
    }
    if (context.elements.compactTrigger) {
        state.triggerClickDisposer = context.resources.addEventListener(context.elements.compactTrigger, 'click', () => toggleCompactPanel(context, state));
    }
};

const unbindCompactTrigger = (state: ChartFiltersCompactModeState): void => {
    if (state.triggerClickDisposer) {
        state.triggerClickDisposer();
        state.triggerClickDisposer = null;
    }
};

const setupCompactMode = (context: ChartFiltersCompactModeContext, state: ChartFiltersCompactModeState): void => {
    if (state.compactChangeDisposer) {
        state.compactChangeDisposer();
        state.compactChangeDisposer = null;
    }
    unbindCompactTrigger(state);

    if (context.config.compactMode === 'always') {
        context.container.dataset['compactFilters'] = 'true';
        bindCompactTrigger(context, state);
        updateCompactSummary(context);
        return;
    }

    const breakpointExclusive = Math.max(0, Math.round(context.config.compactBreakpoint) - 1);
    const applyCompactMode = (matches: boolean): void => {
        context.container.dataset['compactFilters'] = matches ? 'true' : 'false';
        if (matches) {
            bindCompactTrigger(context, state);
            updateCompactSummary(context);
            return;
        }

        unbindCompactTrigger(state);
        context.container.dataset['filtersPanelOpen'] = 'false';
        context.elements.compactTrigger?.setAttribute('aria-expanded', 'false');
        closeCompactPanel(context, state);
    };

    const windowRef = context.container.ownerDocument.defaultView;
    if (!windowRef) throw new Error('Chart filters require a document window');
    const synchronize = (): void => applyCompactMode(measureLayoutViewport(context.container).width <= breakpointExclusive);
    const resizeDisposer = context.resources.addEventListener(windowRef, 'resize', synchronize);
    const scaleDisposer = context.resources.addEventListener(windowRef, INTERFACE_SCALE_CHANGED_EVENT, synchronize);
    state.compactChangeDisposer = (): void => {
        resizeDisposer();
        scaleDisposer();
    };
    synchronize();
};

const disposeCompactMode = (context: ChartFiltersCompactModeContext, state: ChartFiltersCompactModeState): void => {
    if (state.compactChangeDisposer) {
        state.compactChangeDisposer();
        state.compactChangeDisposer = null;
    }
    unbindCompactTrigger(state);
    closeCompactPanel(context, state);
};

const toggleFullscreen = async (context: ChartFiltersFullscreenContext): Promise<void> => {
    const document = dom.getDocument();
    const fullscreenElement = context.fullscreenTarget ? (typeof context.fullscreenTarget === 'string' ? dom.resolve(context.fullscreenTarget, document) : context.fullscreenTarget) : context.container.closest('.history-chart-card, .hardware-insights-card, .chart-container, .card');

    if (!fullscreenElement) {
        return;
    }
    if (document.fullscreenElement) {
        await document.exitFullscreen();
        return;
    }
    await fullscreenElement.requestFullscreen();
};

const updateFullscreenIcon = (context: ChartFiltersFullscreenContext): void => {
    if (!context.button) {
        return;
    }
    const isFullscreen = Boolean(dom.getDocument().fullscreenElement);
    const icon = isFullscreen ? FILTER_ICON_NAMES.FULLSCREEN_EXIT : FILTER_ICON_NAMES.FULLSCREEN_ENTER;
    dom.setHTML(context.button, resolveIconMarkup(icon), { escape: false });
    context.button.setAttribute('aria-pressed', String(isFullscreen));
    context.button.classList.toggle('ui-variant-primary', isFullscreen);
    context.button.classList.toggle('ui-variant-neutral', !isFullscreen);
};

export type { ChartFiltersCompactModeContext, ChartFiltersCompactModeState, ChartFiltersFullscreenContext };
export { closeCompactPanel, createCompactModeState, disposeCompactMode, openCompactPanel, setupCompactMode, toggleCompactPanel, toggleFullscreen, updateCompactSummary, updateFullscreenIcon };
