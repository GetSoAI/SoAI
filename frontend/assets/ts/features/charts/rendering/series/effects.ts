/* SoAI - Charts feature series effects [frontend/assets/ts/features/charts/rendering/series/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PI2 } from '@features/charts/rendering/series/constants.ts';
import type { VisiblePointsWithBuffers } from '@features/charts/renderingTypes.ts';
import { hexToRgba } from '@features/charts/rendering/primitives.ts';

const { isFinite: isFiniteNumber } = Number;

const strokeSplineSegment = (context: CanvasRenderingContext2D, points: VisiblePointsWithBuffers, start: number, end: number, tension: number): void => {
    if (start > end || start < 0) return;
    const { x: xCoordinate, y: yCoordinate } = points;
    if (start === end) {
        const xValue = xCoordinate[start];
        const yValue = yCoordinate[start];
        if (xValue !== undefined && yValue !== undefined) {
            context.beginPath();
            context.arc(xValue, yValue, 1, 0, PI2);
            context.stroke();
        }
        return;
    }
    const xStart = xCoordinate[start];
    const yStart = yCoordinate[start];
    if (xStart === undefined || yStart === undefined) return;
    context.beginPath();
    context.moveTo(xStart, yStart);
    for (let index = start; index < end; index++) {
        const p0x = xCoordinate[index > start ? index - 1 : start];
        const p0y = yCoordinate[index > start ? index - 1 : start];
        const p1x = xCoordinate[index];
        const p1y = yCoordinate[index];
        const p2x = xCoordinate[index + 1];
        const p2y = yCoordinate[index + 1];
        const p3x = xCoordinate[index + 2 <= end ? index + 2 : end];
        const p3y = yCoordinate[index + 2 <= end ? index + 2 : end];

        if (p0x === undefined || p0y === undefined || p1x === undefined || p1y === undefined || p2x === undefined || p2y === undefined || p3x === undefined || p3y === undefined) continue;

        const cp1x = p1x + ((p2x - p0x) / 6) * tension;
        const cp1y = p1y + ((p2y - p0y) / 6) * tension;
        const cp2x = p2x - ((p3x - p1x) / 6) * tension;
        const cp2y = p2y - ((p3y - p1y) / 6) * tension;

        if (isFiniteNumber(cp1x) && isFiniteNumber(cp1y) && isFiniteNumber(cp2x) && isFiniteNumber(cp2y)) {
            context.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2x, p2y);
        } else {
            context.lineTo(p2x, p2y);
        }
    }
    context.stroke();
};

const drawEndpointMarker = (context: CanvasRenderingContext2D, xCoordinate: number, yCoordinate: number, color: string): void => {
    context.save();
    const markerFill = hexToRgba(color, 0.85);
    const markerStroke = hexToRgba(color, 0.55);
    const markerCenter = hexToRgba(color, 0.9);
    context.beginPath();
    context.arc(xCoordinate, yCoordinate, 2.75, 0, PI2);
    context.fillStyle = markerFill;
    context.fill();
    context.lineWidth = 1;
    context.strokeStyle = markerStroke;
    context.stroke();
    context.fillStyle = markerCenter;
    context.beginPath();
    context.arc(xCoordinate, yCoordinate, 1.05, 0, PI2);
    context.fill();
    context.restore();
};

export { drawEndpointMarker, strokeSplineSegment };
