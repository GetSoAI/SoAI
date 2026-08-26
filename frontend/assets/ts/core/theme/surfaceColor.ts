/* SoAI - Surface color normalization and DOM application [frontend/assets/ts/core/theme/surfaceColor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { formatHexColor, hslToRgb, parseHexColor, rgbToHsl } from '@core/theme/colorSpace.ts';
import { normalizeRuntimeHexColorCanonicalOrNull } from '@core/theme/hexColor.ts';

type SurfaceColorTargets = { root: HTMLElement; body?: HTMLElement | null };

const SURFACE_TINT_SATURATION_MAX = 0.25;
const SURFACE_TINT_LIGHTNESS_MIN = 0.2;
const SURFACE_TINT_LIGHTNESS_MAX = 0.55;

const SURFACE_USER_TINT_PROPERTY = '--surface-user-tint';
const SURFACE_USER_TINT_STRENGTH_PROPERTY = '--surface-user-tint-strength';

const normalizeSurfaceColorPreference = (value: JsonValue | undefined): string | null => {
    return normalizeRuntimeHexColorCanonicalOrNull(value);
};

const clampSurfaceTint = (hex: string): string => {
    const tintHsl = rgbToHsl(parseHexColor(hex));
    return formatHexColor(
        hslToRgb({
            hue: tintHsl.hue,
            saturation: Math.min(SURFACE_TINT_SATURATION_MAX, tintHsl.saturation),
            lightness: clampNumber(tintHsl.lightness, SURFACE_TINT_LIGHTNESS_MIN, SURFACE_TINT_LIGHTNESS_MAX)
        })
    ).toLowerCase();
};

const applySurfaceColorToElement = (element: HTMLElement, value: string | null): void => {
    const normalized = normalizeSurfaceColorPreference(value);
    const style = element.style;

    if (!normalized) {
        style.removeProperty(SURFACE_USER_TINT_PROPERTY);
        style.removeProperty(SURFACE_USER_TINT_STRENGTH_PROPERTY);
        return;
    }

    const tint = clampSurfaceTint(normalized);
    style.setProperty(SURFACE_USER_TINT_PROPERTY, tint);
    style.setProperty(SURFACE_USER_TINT_STRENGTH_PROPERTY, '100%');
};

const applySurfaceColor = ({ root, body }: SurfaceColorTargets, value: string | null): void => {
    applySurfaceColorToElement(root, value);
    if (body && body !== root) {
        applySurfaceColorToElement(body, value);
    }
};

export { applySurfaceColor, clampSurfaceTint, normalizeSurfaceColorPreference };
