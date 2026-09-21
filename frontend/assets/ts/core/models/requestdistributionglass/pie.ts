/* SoAI - Shared models pie [frontend/assets/ts/core/models/requestdistributionglass/pie.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestDistributionSlice } from '@core/models/requestDistribution.ts';
import { resolveRequestDistributionColor, toSurfaceColor } from '@core/models/requestDistributionColors.ts';
import { bodyTint, clipPathDef, clipUrl, composeBackground, darkenFace, depthTint, glassFaceMarkup, groundShadowMarkup, lightenFace, nextGlassClipId, radialSpecular, rimPath, roundTo } from '@core/models/requestdistributionglass/glassMaterial.ts';
import type { RequestDistributionGlassInput, RequestDistributionGlassParts } from '@core/models/requestdistributionglass/glassParts.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, joinUiHtml, uiHtml } from '@core/security/uiHtml.ts';

interface PieGeometry {
    centerX: number;
    centerY: number;
    radiusX: number;
    radiusY: number;
    depth: number;
}

const PIE_TILT_RATIO = 0.55;
const PIE_DEPTH_RATIO = 0.14;
const PIE_RADIUS_DIVISOR = 2.6;
const PIE_MAX_RADIUS_Y = 72;
const PIE_MAX_DEPTH = 32;
const TWO_PI = Math.PI * 2;

const computePieGeometry = (width: number, height: number): PieGeometry => {
    const baseRadius = Math.max(1, Math.min(width, height) / PIE_RADIUS_DIVISOR);
    const radiusY = Math.min(baseRadius * PIE_TILT_RATIO, PIE_MAX_RADIUS_Y);
    const depth = clampNumber(width * PIE_DEPTH_RATIO, 4, PIE_MAX_DEPTH);
    const verticalSpan = radiusY * 2 + depth;
    return { centerX: width / 2, centerY: (height - verticalSpan) / 2 + radiusY, radiusX: baseRadius, radiusY, depth };
};

const edgePoint = (geometry: PieGeometry, angle: number, offsetY: number): string => `${roundTo(geometry.centerX + geometry.radiusX * Math.cos(angle))} ${roundTo(geometry.centerY + geometry.radiusY * Math.sin(angle) + offsetY)}`;

const normalizeAngle = (angle: number): number => {
    const wrapped = angle % TWO_PI;
    return wrapped < 0 ? wrapped + TWO_PI : wrapped;
};

const computeFrontSegment = (slice: RequestDistributionSlice): { startAngle: number; endAngle: number } | null => {
    if (slice.endAngle - slice.startAngle >= TWO_PI - 1e-6) {
        return { startAngle: 0, endAngle: Math.PI };
    }
    const start = normalizeAngle(slice.startAngle);
    const end = normalizeAngle(slice.endAngle);
    const arcEnd = start <= end ? end : end + TWO_PI;
    const visibleStart = Math.max(start, 0);
    const visibleEnd = Math.min(arcEnd, Math.PI);
    if (visibleStart >= visibleEnd) {
        if (start > end && 0 < Math.min(end, Math.PI)) {
            return { startAngle: 0, endAngle: Math.min(end, Math.PI) };
        }
        return null;
    }
    return { startAngle: visibleStart, endAngle: visibleEnd };
};

const radii = (geometry: PieGeometry): string => `${roundTo(geometry.radiusX)} ${roundTo(geometry.radiusY)}`;

const buildTopClip = (geometry: PieGeometry, slice: RequestDistributionSlice): TrustedHtml => {
    if (slice.endAngle - slice.startAngle >= TWO_PI - 1e-6) {
        return uiHtml`<ellipse cx="${roundTo(geometry.centerX)}" cy="${roundTo(geometry.centerY)}" rx="${roundTo(geometry.radiusX)}" ry="${roundTo(geometry.radiusY)}" />`;
    }
    const large = slice.endAngle - slice.startAngle > Math.PI ? 1 : 0;
    return uiHtml`<path d="M ${roundTo(geometry.centerX)} ${roundTo(geometry.centerY)} L ${edgePoint(geometry, slice.startAngle, 0)} A ${radii(geometry)} 0 ${large.toString()} 1 ${edgePoint(geometry, slice.endAngle, 0)} Z" />`;
};

const buildSideClip = (geometry: PieGeometry, segment: { startAngle: number; endAngle: number }): TrustedHtml => {
    const large = segment.endAngle - segment.startAngle > Math.PI ? 1 : 0;
    return uiHtml`<path d="M ${edgePoint(geometry, segment.startAngle, 0)} A ${radii(geometry)} 0 ${large.toString()} 1 ${edgePoint(geometry, segment.endAngle, 0)} L ${edgePoint(geometry, segment.endAngle, geometry.depth)} A ${radii(geometry)} 0 ${large.toString()} 0 ${edgePoint(geometry, segment.startAngle, geometry.depth)} Z" />`;
};

const buildTopFace = (geometry: PieGeometry, slice: RequestDistributionSlice, base: string): { def: TrustedHtml; body: TrustedHtml } => {
    const id = nextGlassClipId('pietop');
    const def = clipPathDef(id, buildTopClip(geometry, slice));
    const highlightX = geometry.centerX - geometry.radiusX * 0.25;
    const highlightY = geometry.centerY - geometry.radiusY * 0.5;
    const reach = Math.max(geometry.radiusX, geometry.radiusY) * 1.15;
    const fill = `radial-gradient(circle ${roundTo(reach)}px at ${roundTo(highlightX)}px ${roundTo(highlightY)}px, ${bodyTint(lightenFace(base, 0.16), 58)} 0%, ${bodyTint(base, 52)} 58%, ${depthTint(darkenFace(base, 0.9), 64)} 100%)`;
    const specular = radialSpecular(highlightX, highlightY, reach * 0.62, 30);
    const body = glassFaceMarkup({ background: composeBackground([specular, fill]), clipPath: clipUrl(id), className: null });
    return { def, body };
};

const buildSideWall = (geometry: PieGeometry, slice: RequestDistributionSlice, base: string): { def: TrustedHtml; body: TrustedHtml } | null => {
    const segment = computeFrontSegment(slice);
    if (segment === null) {
        return null;
    }
    const id = nextGlassClipId('pieside');
    const def = clipPathDef(id, buildSideClip(geometry, segment));
    const background = `linear-gradient(180deg, ${depthTint(darkenFace(base, 0.86), 86)} 0%, ${bodyTint(lightenFace(base, 0.22), 52)} 45%, ${depthTint(darkenFace(base, 0.8), 86)} 100%)`;
    const body = glassFaceMarkup({ background, clipPath: clipUrl(id), className: 'distribution-chart-3d__face--depth' });
    return { def, body };
};

const resolveSliceColor = (input: RequestDistributionGlassInput, slice: RequestDistributionSlice): string => {
    const color = resolveRequestDistributionColor(input.colors, slice.swatchIndex, slice.swatchColor);
    if (!color) {
        throw new Error('Request distribution chart color palette is missing an entry');
    }
    return toSurfaceColor(color);
};

const buildPieGlassParts = (input: RequestDistributionGlassInput): RequestDistributionGlassParts => {
    if (input.width <= 0 || input.height <= 0 || input.colors.length === 0 || input.dataset.slices.length === 0) {
        return { defs: EMPTY_UI_HTML, bodies: EMPTY_UI_HTML, rims: EMPTY_UI_HTML };
    }
    const geometry = computePieGeometry(input.width, input.height);
    const defs: TrustedHtml[] = [];
    const bodies: TrustedHtml[] = [groundShadowMarkup({ centerX: geometry.centerX, centerY: geometry.centerY + geometry.depth + geometry.radiusY * 0.5, radiusX: geometry.radiusX * 1.06, radiusY: geometry.radiusY })];
    const rims: TrustedHtml[] = [];
    for (const slice of input.dataset.slices) {
        const wall = buildSideWall(geometry, slice, resolveSliceColor(input, slice));
        if (wall) {
            defs.push(wall.def);
            bodies.push(wall.body);
        }
    }
    for (const slice of input.dataset.slices) {
        const top = buildTopFace(geometry, slice, resolveSliceColor(input, slice));
        defs.push(top.def);
        bodies.push(top.body);
        if (input.dataset.slices.length > 1) {
            rims.push(rimPath(`M ${roundTo(geometry.centerX)} ${roundTo(geometry.centerY)} L ${edgePoint(geometry, slice.startAngle, 0)}`, 'distribution-chart-3d__rim distribution-chart-3d__rim--hairline'));
        }
    }
    rims.push(rimPath(`M ${edgePoint(geometry, 0, geometry.depth)} A ${radii(geometry)} 0 0 1 ${edgePoint(geometry, Math.PI, geometry.depth)}`, 'distribution-chart-3d__rim distribution-chart-3d__rim--separator'));
    return { defs: joinUiHtml(defs), bodies: joinUiHtml(bodies), rims: joinUiHtml(rims) };
};

export { buildPieGlassParts };
