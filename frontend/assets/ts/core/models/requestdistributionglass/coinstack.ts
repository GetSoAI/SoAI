/* SoAI - Shared models coinstack [frontend/assets/ts/core/models/requestdistributionglass/coinstack.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestDistributionEntry } from '@core/models/requestDistribution.ts';
import { toSurfaceColor } from '@core/models/requestDistributionColors.ts';
import { bodyTint, clipPathDef, clipUrl, composeBackground, darkenFace, depthTint, glassFaceMarkup, groundShadowMarkup, lightenFace, nextGlassClipId, radialSpecular, rimEllipse, rimPath, roundTo } from '@core/models/requestdistributionglass/glassMaterial.ts';
import type { RequestDistributionGlassInput, RequestDistributionGlassParts } from '@core/models/requestdistributionglass/glassParts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, joinUiHtml, uiHtml } from '@core/security/uiHtml.ts';

interface CoinPileGeometry {
    centerX: number;
    radiusX: number;
    radiusY: number;
    pileTopY: number;
    pileBaseY: number;
    pileHeight: number;
}

interface CoinBand {
    color: string;
    bottomY: number;
    topY: number;
}

const COIN_PADDING_TOP = 14;
const COIN_PADDING_BOTTOM = 14;
const COIN_PADDING_SIDE = 18;
const COIN_RADIUS_RATIO = 0.32;
const COIN_TILT_RATIO = 0.32;
const COIN_MIN_RADIUS_X = 28;
const COIN_MAX_RADIUS_X = 78;

const computeCoinPileGeometry = (width: number, height: number): CoinPileGeometry | null => {
    const usableWidth = width - COIN_PADDING_SIDE * 2;
    const usableHeight = height - COIN_PADDING_TOP - COIN_PADDING_BOTTOM;
    if (usableWidth <= 0 || usableHeight <= 0) {
        return null;
    }
    const radiusX = Math.max(COIN_MIN_RADIUS_X, Math.min(COIN_MAX_RADIUS_X, Math.min(usableWidth * COIN_RADIUS_RATIO, usableWidth / 2)));
    const radiusY = radiusX * COIN_TILT_RATIO;
    const pileHeight = usableHeight - radiusY * 2;
    if (pileHeight <= radiusY) {
        return null;
    }
    const pileTopY = COIN_PADDING_TOP + radiusY;
    return { centerX: width / 2, radiusX, radiusY, pileTopY, pileBaseY: pileTopY + pileHeight, pileHeight };
};

const buildCoinBands = (entries: readonly RequestDistributionEntry[], colors: readonly string[], geometry: CoinPileGeometry): CoinBand[] => {
    const totalValue = entries.reduce((sum, entry) => sum + entry.value, 0);
    if (totalValue <= 0) {
        return [];
    }
    const bands: CoinBand[] = [];
    let cursorY = geometry.pileBaseY;
    for (const entry of entries) {
        const bandHeight = (entry.value / totalValue) * geometry.pileHeight;
        const resolvedColor = colors[entry.swatchIndex % colors.length];
        if (!resolvedColor) {
            throw new Error('Request distribution chart color palette is missing an entry');
        }
        bands.push({ color: toSurfaceColor(resolvedColor), bottomY: cursorY, topY: cursorY - bandHeight });
        cursorY -= bandHeight;
    }
    return bands;
};

const bandSidePath = (geometry: CoinPileGeometry, band: CoinBand): string => {
    const leftX = roundTo(geometry.centerX - geometry.radiusX);
    const rightX = roundTo(geometry.centerX + geometry.radiusX);
    const radii = `${roundTo(geometry.radiusX)} ${roundTo(geometry.radiusY)}`;
    return `M ${leftX} ${roundTo(band.topY)} A ${radii} 0 0 0 ${rightX} ${roundTo(band.topY)} L ${rightX} ${roundTo(band.bottomY)} A ${radii} 0 0 1 ${leftX} ${roundTo(band.bottomY)} Z`;
};

const frontArc = (centerX: number, yCoordinate: number, radiusX: number, radiusY: number): string => `M ${roundTo(centerX - radiusX)} ${roundTo(yCoordinate)} A ${roundTo(radiusX)} ${roundTo(radiusY)} 0 0 0 ${roundTo(centerX + radiusX)} ${roundTo(yCoordinate)}`;

const buildBandSide = (geometry: CoinPileGeometry, band: CoinBand): { def: TrustedHtml; body: TrustedHtml } => {
    const id = nextGlassClipId('coin');
    const def = clipPathDef(id, uiHtml`<path d="${bandSidePath(geometry, band)}" />`);
    const background = `linear-gradient(90deg, ${depthTint(darkenFace(band.color, 0.7), 84)} 0%, ${bodyTint(lightenFace(band.color, 0.24), 54)} 50%, ${depthTint(darkenFace(band.color, 0.76), 84)} 100%)`;
    const body = glassFaceMarkup({ background, clipPath: clipUrl(id), className: 'distribution-chart-3d__face--depth' });
    return { def, body };
};

const buildTopCap = (geometry: CoinPileGeometry, band: CoinBand): { def: TrustedHtml; body: TrustedHtml; rim: TrustedHtml } => {
    const id = nextGlassClipId('coincap');
    const def = clipPathDef(id, uiHtml`<ellipse cx="${roundTo(geometry.centerX)}" cy="${roundTo(band.topY)}" rx="${roundTo(geometry.radiusX)}" ry="${roundTo(geometry.radiusY)}" />`);
    const specular = radialSpecular(geometry.centerX - geometry.radiusX * 0.35, band.topY - geometry.radiusY * 0.45, geometry.radiusX, 62);
    const fill = `radial-gradient(circle ${roundTo(geometry.radiusX)}px at ${roundTo(geometry.centerX)}px ${roundTo(band.topY)}px, ${bodyTint(lightenFace(band.color, 0.36), 58)} 0%, ${bodyTint(band.color, 52)} 100%)`;
    const body = glassFaceMarkup({ background: composeBackground([specular, fill]), clipPath: clipUrl(id), className: null });
    const rim = rimEllipse(geometry.centerX, band.topY, geometry.radiusX, geometry.radiusY, 'distribution-chart-3d__rim distribution-chart-3d__rim--bright');
    return { def, body, rim };
};

const buildCoinstackGlassParts = (input: RequestDistributionGlassInput): RequestDistributionGlassParts => {
    if (input.width <= 0 || input.height <= 0 || input.colors.length === 0 || input.dataset.entries.length === 0) {
        return { defs: EMPTY_UI_HTML, bodies: EMPTY_UI_HTML, rims: EMPTY_UI_HTML };
    }
    const geometry = computeCoinPileGeometry(input.width, input.height);
    if (geometry === null) {
        return { defs: EMPTY_UI_HTML, bodies: EMPTY_UI_HTML, rims: EMPTY_UI_HTML };
    }
    const bands = buildCoinBands(input.dataset.entries, input.colors, geometry);
    if (bands.length === 0) {
        return { defs: EMPTY_UI_HTML, bodies: EMPTY_UI_HTML, rims: EMPTY_UI_HTML };
    }
    const defs: TrustedHtml[] = [];
    const bodies: TrustedHtml[] = [groundShadowMarkup({ centerX: geometry.centerX, centerY: geometry.pileBaseY + geometry.radiusY * 0.6, radiusX: geometry.radiusX * 1.05, radiusY: geometry.radiusY * 0.95 })];
    const rims: TrustedHtml[] = [];
    for (const band of bands) {
        const side = buildBandSide(geometry, band);
        defs.push(side.def);
        bodies.push(side.body);
    }
    for (let index = 0; index < bands.length - 1; index += 1) {
        const upper = bands[index + 1];
        if (!upper) {
            continue;
        }
        rims.push(rimPath(frontArc(geometry.centerX, upper.bottomY, geometry.radiusX, geometry.radiusY), 'distribution-chart-3d__rim distribution-chart-3d__rim--separator'));
    }
    const topBand = bands[bands.length - 1];
    if (topBand) {
        const cap = buildTopCap(geometry, topBand);
        defs.push(cap.def);
        bodies.push(cap.body);
        rims.push(cap.rim);
    }
    return { defs: joinUiHtml(defs), bodies: joinUiHtml(bodies), rims: joinUiHtml(rims) };
};

export { buildCoinstackGlassParts };
