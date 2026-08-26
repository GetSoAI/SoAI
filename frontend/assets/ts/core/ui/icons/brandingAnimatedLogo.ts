/* SoAI - Shared UI branding animated logo [frontend/assets/ts/core/ui/icons/brandingAnimatedLogo.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber, isString } from '@core/typeGuards.ts';

let animatedBrandLogoSequence = 0;

const DOT_RADIUS = 7.5;
const GRID_SPACING = 22;
const OUTER_RING_RADIUS = 81.5;
const OUTER_RING_STROKE_WIDTH = 17;
const OUTER_BORDER_RADIUS = 90;
const INNER_BORDER_RADIUS = 73;
const DOT_LAYOUT: readonly { x: number; y: number; ring: 1 | 2 | 3 | 4 }[] = Object.freeze([
    { x: 100 - GRID_SPACING, y: 100, ring: 1 },
    { x: 100 + GRID_SPACING, y: 100, ring: 1 },
    { x: 100, y: 100 - GRID_SPACING, ring: 1 },
    { x: 100, y: 100 + GRID_SPACING, ring: 1 },
    { x: 100 - GRID_SPACING, y: 100 - GRID_SPACING, ring: 2 },
    { x: 100 + GRID_SPACING, y: 100 - GRID_SPACING, ring: 2 },
    { x: 100 - GRID_SPACING, y: 100 + GRID_SPACING, ring: 2 },
    { x: 100 + GRID_SPACING, y: 100 + GRID_SPACING, ring: 2 },
    { x: 100 - GRID_SPACING * 2, y: 100, ring: 3 },
    { x: 100 + GRID_SPACING * 2, y: 100, ring: 3 },
    { x: 100, y: 100 - GRID_SPACING * 2, ring: 3 },
    { x: 100, y: 100 + GRID_SPACING * 2, ring: 3 },
    { x: 100 - GRID_SPACING, y: 100 - GRID_SPACING * 2, ring: 4 },
    { x: 100 + GRID_SPACING, y: 100 - GRID_SPACING * 2, ring: 4 },
    { x: 100 - GRID_SPACING * 2, y: 100 - GRID_SPACING, ring: 4 },
    { x: 100 + GRID_SPACING * 2, y: 100 - GRID_SPACING, ring: 4 },
    { x: 100 - GRID_SPACING * 2, y: 100 + GRID_SPACING, ring: 4 },
    { x: 100 + GRID_SPACING * 2, y: 100 + GRID_SPACING, ring: 4 },
    { x: 100 - GRID_SPACING, y: 100 + GRID_SPACING * 2, ring: 4 },
    { x: 100 + GRID_SPACING, y: 100 + GRID_SPACING * 2, ring: 4 }
]);

type AnimatedBrandLogoVariant = 'pico' | 'small';

interface AnimatedBrandLogoMarkupOptions {
    className?: string;
    durationMs?: number;
    variant?: AnimatedBrandLogoVariant;
}

const resolveAnimatedBrandLogoVariant = (variant: AnimatedBrandLogoVariant | undefined): AnimatedBrandLogoVariant => {
    if (variant === 'pico' || variant === 'small') {
        return variant;
    }
    return 'small';
};

const buildAnimatedBrandLogoClassName = (variant: AnimatedBrandLogoVariant, className: string | undefined): string => {
    const classNames = ['soai-animated-logo', `soai-animated-logo--${variant}`, 'soai-animated-logo--loading'];
    if (isString(className) && className.trim()) {
        classNames.push(className.trim());
    }
    return classNames.join(' ');
};

const resolveAnimatedBrandLogoDurationStyle = (durationMs: number | undefined): string => {
    if (!isNumber(durationMs) || !Number.isFinite(durationMs) || durationMs <= 0) {
        return '';
    }
    return ` style="--soai-animated-logo-duration:${String(durationMs / 1000)}s"`;
};

const nextAnimatedBrandLogoIdPrefix = (): string => {
    animatedBrandLogoSequence += 1;
    return `soai-animated-logo-${String(animatedBrandLogoSequence)}`;
};

const renderAnimatedBrandLogoDots = (): string => {
    return DOT_LAYOUT.map((dot) => `<circle cx="${String(dot.x)}" cy="${String(dot.y)}" r="${String(DOT_RADIUS)}" class="soai-animated-logo__dot soai-animated-logo__dot--ring-${String(dot.ring)}" />`).join('');
};

const renderAnimatedBrandSmallLogoMarkup = (options: AnimatedBrandLogoMarkupOptions = {}): string => {
    const variant = resolveAnimatedBrandLogoVariant(options.variant);
    const idPrefix = nextAnimatedBrandLogoIdPrefix();
    const gradientId = `${idPrefix}-ring-gradient`;
    const filterId = `${idPrefix}-ring-bevel`;
    const durationStyle = resolveAnimatedBrandLogoDurationStyle(options.durationMs);
    const className = buildAnimatedBrandLogoClassName(variant, options.className);
    const dots = renderAnimatedBrandLogoDots();
    return `<span class="${className}" data-soai-animated-logo="${variant}" aria-hidden="true"><svg class="soai-animated-logo__svg" viewBox="0 0 200 200" focusable="false" xmlns="http://www.w3.org/2000/svg"${durationStyle}><defs><radialGradient id="${gradientId}" cx="50%" cy="50%" r="50%" gradientUnits="userSpaceOnUse"><stop offset="72%" style="stop-color:var(--soai-animated-logo-ring-edge)" /><stop offset="81.5%" style="stop-color:var(--soai-animated-logo-ring-mid)" /><stop offset="91%" style="stop-color:var(--soai-animated-logo-ring-edge)" /></radialGradient><filter id="${filterId}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur in="SourceAlpha" stdDeviation="1.5" result="blur" /><feOffset dx="1" dy="1" result="offset" /><feComposite in="SourceGraphic" in2="offset" operator="over" /></filter></defs><circle cx="100" cy="100" r="${String(OUTER_RING_RADIUS)}" fill="none" stroke="url(#${gradientId})" stroke-width="${String(OUTER_RING_STROKE_WIDTH)}" filter="url(#${filterId})" /><circle cx="100" cy="100" r="${String(OUTER_BORDER_RADIUS)}" fill="none" stroke="var(--soai-animated-logo-ring-border)" stroke-width="1" opacity="0.25" /><circle cx="100" cy="100" r="${String(INNER_BORDER_RADIUS)}" fill="none" stroke="var(--soai-animated-logo-ring-border)" stroke-width="1" opacity="0.25" />${dots}<circle cx="100" cy="100" r="${String(DOT_RADIUS)}" class="soai-animated-logo__center" /></svg></span>`;
};

const renderAnimatedBrandPicoLogoMarkup = (options: Omit<AnimatedBrandLogoMarkupOptions, 'variant'> = {}): string => {
    return renderAnimatedBrandSmallLogoMarkup({
        ...options,
        variant: 'pico'
    });
};

export { renderAnimatedBrandPicoLogoMarkup, renderAnimatedBrandSmallLogoMarkup };
export type { AnimatedBrandLogoMarkupOptions, AnimatedBrandLogoVariant };
