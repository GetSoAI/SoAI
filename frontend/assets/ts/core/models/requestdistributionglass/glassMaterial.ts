/* SoAI - Shared models glass material [frontend/assets/ts/core/models/requestdistributionglass/glassMaterial.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { darkenHexColor, lightenHexColor } from '@core/models/requestDistributionColors.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { clipPathDef, rimCircle, rimEllipse, rimPath, vectorOverlayMarkup } from '@core/ui/icons/requestDistributionVectorMarkup.ts';

interface GlassFaceMarkupOptions {
    background: string;
    clipPath: string;
    className: string | null;
}

interface GroundShadowOptions {
    centerX: number;
    centerY: number;
    radiusX: number;
    radiusY: number;
}

const FACE_CLASS = 'distribution-chart-3d__face';
const GROUND_CLASS = 'distribution-chart-3d__ground';
const FACE_BODY_OPACITY = 92;
const FACE_DEPTH_OPACITY = 95;
const HUE_PRESENCE_BOOST = 34;

let glassClipSequence = 0;

const roundTo = (value: number): string => (Math.round(value * 100) / 100).toString();

const nextGlassClipId = (prefix: string): string => {
    glassClipSequence += 1;
    return `rd-${prefix}-${glassClipSequence.toString()}`;
};

const translucent = (color: string, opacityPercent: number): string => `color-mix(in srgb, ${color} ${roundTo(opacityPercent)}%, transparent)`;

const clampPercent = (value: number): number => Math.max(0, Math.min(96, value));

const glassTint = (hex: string, presencePercent: number, opacityPercent: number): string => translucent(`color-mix(in srgb, ${hex} ${roundTo(clampPercent(presencePercent + HUE_PRESENCE_BOOST))}%, var(--glass-surface-strong))`, opacityPercent);

const bodyTint = (hex: string, presencePercent: number): string => glassTint(hex, presencePercent, FACE_BODY_OPACITY);
const depthTint = (hex: string, presencePercent: number): string => glassTint(hex, presencePercent, FACE_DEPTH_OPACITY);

const topSheen = (): string => 'linear-gradient(151deg, color-mix(in srgb, var(--color-white) 46%, transparent) 0%, color-mix(in srgb, var(--color-white) 12%, transparent) 26%, transparent 50%)';

const verticalSheen = (): string => 'linear-gradient(180deg, color-mix(in srgb, var(--color-white) 38%, transparent) 0%, transparent 38%, color-mix(in srgb, var(--color-black) 14%, transparent) 100%)';

const radialSpecular = (centerX: number, centerY: number, radius: number, corePercent: number): string => `radial-gradient(circle ${roundTo(radius)}px at ${roundTo(centerX)}px ${roundTo(centerY)}px, color-mix(in srgb, var(--color-white) ${roundTo(corePercent)}%, transparent) 0%, transparent 70%)`;

const lightenFace = (hex: string, amount: number): string => lightenHexColor(hex, amount);
const darkenFace = (hex: string, factor: number): string => darkenHexColor(hex, factor);

const composeBackground = (layers: readonly string[]): string => layers.join(', ');

const glassFaceMarkup = (options: GlassFaceMarkupOptions): TrustedHtml => {
    const className = options.className === null ? FACE_CLASS : `${FACE_CLASS} ${options.className}`;
    const clip = options.clipPath;
    return uiHtml`<div class="${className}" style="clip-path:${clip};-webkit-clip-path:${clip};background:${options.background}"></div>`;
};

const clipUrl = (id: string): string => `url(#${id})`;

const groundShadowMarkup = (options: GroundShadowOptions): TrustedHtml => {
    const left = roundTo(options.centerX - options.radiusX);
    const top = roundTo(options.centerY - options.radiusY);
    const width = roundTo(options.radiusX * 2);
    const height = roundTo(options.radiusY * 2);
    return uiHtml`<div class="${GROUND_CLASS}" style="left:${left}px;top:${top}px;width:${width}px;height:${height}px"></div>`;
};

export { bodyTint, clipPathDef, clipUrl, composeBackground, darkenFace, depthTint, glassFaceMarkup, groundShadowMarkup, lightenFace, nextGlassClipId, radialSpecular, rimCircle, rimEllipse, rimPath, roundTo, topSheen, vectorOverlayMarkup, verticalSheen };
