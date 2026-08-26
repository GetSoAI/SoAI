/* SoAI - Charts feature interaction state [frontend/assets/ts/features/charts/interaction/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { INTERACTION_CLASS_MAP } from '@core/charts/constants.ts';
import { dom } from '@core/dom/dom.ts';
import type { PointerState } from '@features/charts/chartTypes.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';

let interactionClassListCache: string[] | null = null;

type InteractionMode = 'pan' | 'xAxis' | 'yAxis';

const setInteractionMode = (chart: ChartInteractionScene, mode: InteractionMode | null): void => {
    const canvas = chart.surface.canvasLayers.interaction;
    if (!canvas) {
        throw new Error('Chart requires an interaction canvas to update interaction mode');
    }
    const activeClass = mode ? INTERACTION_CLASS_MAP[mode] : null;
    const classes = interactionClassListCache || (interactionClassListCache = Object.values(INTERACTION_CLASS_MAP));
    for (const interactionClass of classes) {
        dom.toggleClass(canvas, interactionClass, interactionClass === activeClass);
    }
};

const requirePointerState = (chart: ChartInteractionScene): PointerState => {
    const state = chart.interaction.pointer;
    if (!state) {
        throw new Error('Chart requires pointer state before handling pointer events');
    }
    return state;
};

const resetDragState = (chart: ChartInteractionScene): void => {
    const { yAxisDrag, xAxisDrag } = chart.interaction;
    const { pan } = chart.viewportState;
    yAxisDrag.active = xAxisDrag.active = pan.isDragging = pan.isZooming = false;
    pan.velocity = 0;
    pan.lastX = pan.lastY = 0;
    pan.startOffset = pan.targetOffset = pan.offset;
    setInteractionMode(chart, null);
};

export { requirePointerState, resetDragState, setInteractionMode };
