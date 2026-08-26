/* SoAI - Shared models spheres [frontend/assets/ts/core/models/requestdistributionglass/spheres.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toSurfaceColor } from '@core/models/requestDistributionColors.ts';
import { bodyTint, composeBackground, darkenFace, depthTint, glassFaceMarkup, groundShadowMarkup, lightenFace, radialSpecular, roundTo } from '@core/models/requestdistributionglass/glassMaterial.ts';
import type { RequestDistributionGlassInput, RequestDistributionGlassParts } from '@core/models/requestdistributionglass/glassParts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, joinUiHtml } from '@core/security/uiHtml.ts';

interface SphereLayoutCell {
    centerX: number;
    centerY: number;
    cellRadius: number;
}

const SPHERES_PADDING = 14;
const SPHERES_MIN_RADIUS_RATIO = 0.32;
const SPHERES_CELL_PADDING_RATIO = 0.78;
const SPHERES_MAX_VISIBLE = 16;

const computeGridDimensions = (count: number, width: number, height: number): { columns: number; rows: number } => {
    if (count <= 0) {
        return { columns: 1, rows: 1 };
    }
    const aspect = Math.max(0.5, width / Math.max(1, height));
    const columns = Math.max(1, Math.min(count, Math.round(Math.sqrt(count * aspect))));
    const rows = Math.max(1, Math.ceil(count / columns));
    return { columns, rows };
};

const layoutSphereCells = (count: number, width: number, height: number): SphereLayoutCell[] => {
    const { columns, rows } = computeGridDimensions(count, width - SPHERES_PADDING * 2, height - SPHERES_PADDING * 2);
    const usableWidth = width - SPHERES_PADDING * 2;
    const usableHeight = height - SPHERES_PADDING * 2;
    const cellWidth = usableWidth / columns;
    const cellHeight = usableHeight / rows;
    const cellRadius = Math.max(4, (Math.min(cellWidth, cellHeight) / 2) * SPHERES_CELL_PADDING_RATIO);
    const cells: SphereLayoutCell[] = [];
    for (let index = 0; index < count; index += 1) {
        const column = index % columns;
        const row = Math.floor(index / columns);
        const rowItemCount = row === rows - 1 ? count - row * columns : columns;
        const rowOffset = (columns - rowItemCount) * cellWidth * 0.5;
        const centerX = SPHERES_PADDING + rowOffset + cellWidth * (column + 0.5);
        const centerY = SPHERES_PADDING + cellHeight * (row + 0.5);
        cells.push({ centerX, centerY, cellRadius });
    }
    return cells;
};

const resolveSphereRadius = (cell: SphereLayoutCell, valueRatio: number): number => {
    const minRadius = cell.cellRadius * SPHERES_MIN_RADIUS_RATIO;
    return Math.max(minRadius, cell.cellRadius * Math.sqrt(Math.max(0, valueRatio)));
};

const buildSphereBody = (cell: SphereLayoutCell, radius: number, base: string): TrustedHtml => {
    const highlightX = cell.centerX - radius * 0.35;
    const highlightY = cell.centerY - radius * 0.4;
    const body = `radial-gradient(circle ${roundTo(radius * 1.08)}px at ${roundTo(cell.centerX)}px ${roundTo(cell.centerY)}px, ${bodyTint(lightenFace(base, 0.12), 56)} 26%, ${bodyTint(base, 52)} 66%, ${depthTint(darkenFace(base, 0.6), 78)} 100%)`;
    const specular = radialSpecular(highlightX, highlightY, radius * 0.52, 80);
    const clip = `circle(${roundTo(radius)}px at ${roundTo(cell.centerX)}px ${roundTo(cell.centerY)}px)`;
    return glassFaceMarkup({ background: composeBackground([specular, body]), clipPath: clip, className: 'distribution-chart-3d__face--sphere' });
};

const buildPart = (cell: SphereLayoutCell, radius: number, base: string): { body: TrustedHtml; ground: TrustedHtml } => {
    const ground = groundShadowMarkup({ centerX: cell.centerX, centerY: cell.centerY + radius * 0.94, radiusX: radius * 0.82, radiusY: radius * 0.24 });
    const body = buildSphereBody(cell, radius, base);
    return { body, ground };
};

const buildSpheresGlassParts = (input: RequestDistributionGlassInput): RequestDistributionGlassParts => {
    if (input.width <= 0 || input.height <= 0 || input.colors.length === 0 || input.dataset.entries.length === 0) {
        return { defs: EMPTY_UI_HTML, bodies: EMPTY_UI_HTML, rims: EMPTY_UI_HTML };
    }
    const entries = input.dataset.entries.slice(0, SPHERES_MAX_VISIBLE);
    const cells = layoutSphereCells(entries.length, input.width, input.height);
    const maxValue = entries.reduce((max, entry) => (entry.value > max ? entry.value : max), 0);
    const grounds: TrustedHtml[] = [];
    const bodies: TrustedHtml[] = [];
    entries.forEach((entry, index) => {
        const color = input.colors[entry.swatchIndex % input.colors.length];
        if (!color) {
            throw new Error('Request distribution chart color palette is missing an entry');
        }
        const cell = cells[index];
        if (!cell) {
            return;
        }
        const valueRatio = maxValue > 0 ? entry.value / maxValue : 0;
        const radius = resolveSphereRadius(cell, valueRatio);
        const part = buildPart(cell, radius, toSurfaceColor(color));
        grounds.push(part.ground);
        bodies.push(part.body);
    });
    return { defs: EMPTY_UI_HTML, bodies: joinUiHtml([...grounds, ...bodies]), rims: EMPTY_UI_HTML };
};

export { buildSpheresGlassParts };
