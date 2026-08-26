/* SoAI - Shared UI tooltip positioning [frontend/assets/ts/core/ui/tooltips/tooltipPositioning.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';

const positionTooltipElement = (inputArguments: { target: Element; tooltipElement: HTMLDivElement }): void => {
    const rect = measureLayoutBox(inputArguments.target);

    const tooltipRect = measureLayoutBox(inputArguments.tooltipElement);
    const viewport = measureLayoutViewport(inputArguments.target);
    const viewportWidth = Math.max(0, viewport.width);
    const viewportHeight = Math.max(0, viewport.height);
    const offset = 10;
    const edgePadding = 10;

    const centeredX = rect.left + rect.width / 2 - tooltipRect.width / 2;
    const xCoordinate = clampNumber(centeredX, edgePadding, Math.max(edgePadding, viewportWidth - tooltipRect.width - edgePadding));

    const aboveY = rect.top - tooltipRect.height - offset;
    const belowY = rect.bottom + offset;
    const yCoordinate = aboveY >= edgePadding ? aboveY : clampNumber(belowY, edgePadding, Math.max(edgePadding, viewportHeight - tooltipRect.height - edgePadding));

    dom.setStyle(inputArguments.tooltipElement, 'left', `${xCoordinate}px`);
    dom.setStyle(inputArguments.tooltipElement, 'top', `${yCoordinate}px`);
};

export { positionTooltipElement };
