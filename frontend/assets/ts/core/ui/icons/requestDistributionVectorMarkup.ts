/* SoAI - Request distribution vector markup [frontend/assets/ts/core/ui/icons/requestDistributionVectorMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML, uiHtml } from '@core/security/uiHtml.ts';

const VECTOR_CLASS = 'distribution-chart-3d__vector';

const formatVectorNumber = (value: number): string => (Math.round(value * 100) / 100).toString();

const clipPathDef = (id: string, shape: TrustedHtml): TrustedHtml => uiHtml`<clipPath id="${id}" clipPathUnits="userSpaceOnUse">${shape}</clipPath>`;

const rimPath = (definition: string, className: string): TrustedHtml => uiHtml`<path d="${definition}" class="${className}" fill="none" />`;

const rimEllipse = (centerX: number, centerY: number, radiusX: number, radiusY: number, className: string): TrustedHtml => uiHtml`<ellipse cx="${formatVectorNumber(centerX)}" cy="${formatVectorNumber(centerY)}" rx="${formatVectorNumber(radiusX)}" ry="${formatVectorNumber(radiusY)}" class="${className}" fill="none" />`;

const rimCircle = (centerX: number, centerY: number, radius: number, className: string): TrustedHtml => uiHtml`<circle cx="${formatVectorNumber(centerX)}" cy="${formatVectorNumber(centerY)}" r="${formatVectorNumber(radius)}" class="${className}" fill="none" />`;

const vectorOverlayMarkup = (width: number, height: number, defs: TrustedHtml, rims: TrustedHtml): TrustedHtml => {
    const defsBlock = defs.html ? uiHtml`<defs>${defs}</defs>` : EMPTY_UI_HTML;
    return uiHtml`<svg class="${VECTOR_CLASS}" viewBox="0 0 ${formatVectorNumber(width)} ${formatVectorNumber(height)}" preserveAspectRatio="none" aria-hidden="true" focusable="false">${defsBlock}${rims}</svg>`;
};

export { clipPathDef, rimCircle, rimEllipse, rimPath, vectorOverlayMarkup };
