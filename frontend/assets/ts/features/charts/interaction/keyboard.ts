/* SoAI - Charts feature keyboard [frontend/assets/ts/features/charts/interaction/keyboard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hideCrosshair } from '@features/charts/crosshair.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';
import { panBySlots, resetViewport, snapshotViewportToLatest, applyZoomAtRatio } from '@features/charts/interaction/viewportCommands.ts';

const KEYBOARD_ZOOM_FACTOR = 1.18;

const handleKeyboardNavigation = (chart: ChartInteractionScene, event: KeyboardEvent): void => {
    let handled = true;
    const dataSlots = chart.viewport.getSlotMetrics().dataSlots;
    switch (event.key) {
        case 'ArrowLeft':
            panBySlots(chart, -Math.max(1, Math.ceil(dataSlots * 0.12)));
            break;
        case 'ArrowRight':
            panBySlots(chart, Math.max(1, Math.ceil(dataSlots * 0.12)));
            break;
        case '+':
        case '=':
            chart.viewport.markManual('keyboard');
            applyZoomAtRatio(chart, { level: chart.viewportState.zoom.level * KEYBOARD_ZOOM_FACTOR, anchorRatio: 0.5, source: 'keyboard', animate: true });
            break;
        case '-':
            chart.viewport.markManual('keyboard');
            applyZoomAtRatio(chart, { level: chart.viewportState.zoom.level / KEYBOARD_ZOOM_FACTOR, anchorRatio: 0.5, source: 'keyboard', animate: true });
            break;
        case '0':
            resetViewport(chart, false);
            break;
        case 'End':
            snapshotViewportToLatest(chart);
            break;
        case 'Escape':
            hideCrosshair(chart);
            break;
        default:
            handled = false;
    }
    if (handled) {
        event.preventDefault();
    }
};

export { handleKeyboardNavigation };
