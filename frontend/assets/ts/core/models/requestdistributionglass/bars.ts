/* SoAI - Shared models bars [frontend/assets/ts/core/models/requestdistributionglass/bars.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestDistributionEntry } from '@core/models/requestDistribution.ts';
import { resolveRequestDistributionColor, toSurfaceColor } from '@core/models/requestDistributionColors.ts';
import { bodyTint, composeBackground, darkenFace, depthTint, glassFaceMarkup, lightenFace, roundTo, topSheen } from '@core/models/requestdistributionglass/glassMaterial.ts';
import type { RequestDistributionGlassInput, RequestDistributionGlassParts } from '@core/models/requestdistributionglass/glassParts.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, joinUiHtml } from '@core/security/uiHtml.ts';

interface BarGeometry {
    barWidth: number;
    barGap: number;
    depthX: number;
    depthY: number;
    baselineY: number;
    plotLeft: number;
    plotHeight: number;
}

interface BarFaces {
    leftX: number;
    rightX: number;
    topY: number;
    backLeftX: number;
    backRightX: number;
    backTopY: number;
    backBaselineY: number;
}

const BARS_PADDING_TOP = 14;
const BARS_PADDING_BOTTOM = 18;
const BARS_PADDING_SIDE = 16;
const BARS_GAP_RATIO = 0.32;
const BARS_DEPTH_RATIO = 0.55;
const BARS_MAX_DEPTH = 18;
const BARS_MIN_DEPTH = 6;
const computeBarGeometry = (width: number, height: number, count: number): BarGeometry | null => {
    const usableWidth = width - BARS_PADDING_SIDE * 2;
    const usableHeight = height - BARS_PADDING_TOP - BARS_PADDING_BOTTOM;
    if (usableWidth <= 0 || usableHeight <= 0 || count <= 0) {
        return null;
    }
    const slotWidth = usableWidth / count;
    const barWidth = Math.max(4, slotWidth * (1 - BARS_GAP_RATIO));
    const barGap = slotWidth - barWidth;
    const depth = clampNumber(barWidth * BARS_DEPTH_RATIO, BARS_MIN_DEPTH, BARS_MAX_DEPTH);
    const baselineY = height - BARS_PADDING_BOTTOM;
    const plotHeight = usableHeight - depth * 0.7;
    if (plotHeight <= 0) {
        return null;
    }
    return { barWidth, barGap, depthX: depth, depthY: depth * 0.7, baselineY, plotLeft: BARS_PADDING_SIDE, plotHeight };
};

const resolveBarFaces = (geometry: BarGeometry, index: number, ratio: number): BarFaces => {
    const slotWidth = geometry.barWidth + geometry.barGap;
    const leftX = geometry.plotLeft + geometry.barGap / 2 + index * slotWidth;
    const barHeight = Math.max(2, geometry.plotHeight * ratio);
    const topY = geometry.baselineY - barHeight;
    const rightX = leftX + geometry.barWidth;
    return {
        leftX,
        rightX,
        topY,
        backLeftX: leftX + geometry.depthX,
        backRightX: rightX + geometry.depthX,
        backTopY: topY - geometry.depthY,
        backBaselineY: geometry.baselineY - geometry.depthY
    };
};

const polygon = (points: ReadonlyArray<readonly [number, number]>): string => `polygon(${points.map(([xCoordinate, yCoordinate]) => `${roundTo(xCoordinate)}px ${roundTo(yCoordinate)}px`).join(', ')})`;

const buildBar = (faces: BarFaces, baselineY: number, base: string): TrustedHtml => {
    const sideClip = polygon([
        [faces.rightX, faces.topY],
        [faces.backRightX, faces.backTopY],
        [faces.backRightX, faces.backBaselineY],
        [faces.rightX, baselineY]
    ]);
    const topClip = polygon([
        [faces.leftX, faces.topY],
        [faces.backLeftX, faces.backTopY],
        [faces.backRightX, faces.backTopY],
        [faces.rightX, faces.topY]
    ]);
    const frontClip = polygon([
        [faces.leftX, faces.topY],
        [faces.rightX, faces.topY],
        [faces.rightX, baselineY],
        [faces.leftX, baselineY]
    ]);
    const sideFace = glassFaceMarkup({ background: depthTint(darkenFace(base, 0.66), 82), clipPath: sideClip, className: 'distribution-chart-3d__face--depth' });
    const topFace = glassFaceMarkup({ background: bodyTint(lightenFace(base, 0.34), 60), clipPath: topClip, className: null });
    const frontBackground = composeBackground([topSheen(), `linear-gradient(180deg, ${bodyTint(lightenFace(base, 0.3), 58)} 0%, ${bodyTint(base, 52)} 55%, ${depthTint(darkenFace(base, 0.86), 70)} 100%)`]);
    const frontFace = glassFaceMarkup({ background: frontBackground, clipPath: frontClip, className: null });
    return joinUiHtml([sideFace, topFace, frontFace]);
};

const buildBarsGlassParts = (input: RequestDistributionGlassInput): RequestDistributionGlassParts => {
    if (input.width <= 0 || input.height <= 0 || input.colors.length === 0 || input.dataset.entries.length === 0) {
        return { defs: EMPTY_UI_HTML, bodies: EMPTY_UI_HTML, rims: EMPTY_UI_HTML };
    }
    const entries: readonly RequestDistributionEntry[] = input.dataset.entries;
    const geometry = computeBarGeometry(input.width, input.height, entries.length);
    if (geometry === null) {
        return { defs: EMPTY_UI_HTML, bodies: EMPTY_UI_HTML, rims: EMPTY_UI_HTML };
    }
    const maxValue = entries.reduce((max, entry) => (entry.value > max ? entry.value : max), 0);
    const bodies: TrustedHtml[] = [];
    entries.forEach((entry, index) => {
        const color = resolveRequestDistributionColor(input.colors, entry.swatchIndex, entry.swatchColor);
        if (!color) {
            throw new Error('Request distribution chart color palette is missing an entry');
        }
        const ratio = maxValue > 0 ? entry.value / maxValue : 0;
        const faces = resolveBarFaces(geometry, index, ratio);
        bodies.push(buildBar(faces, geometry.baselineY, toSurfaceColor(color)));
    });
    return { defs: EMPTY_UI_HTML, bodies: joinUiHtml(bodies), rims: EMPTY_UI_HTML };
};

export { buildBarsGlassParts };
