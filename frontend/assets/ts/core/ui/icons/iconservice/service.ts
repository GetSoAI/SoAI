/* SoAI - Shared UI icon service implementation [frontend/assets/ts/core/ui/icons/iconservice/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { toTrustedSvg } from '@core/security/public.ts';
import { isInstanceOf, isNullOrUndefined, hasOwn } from '@core/typeGuards.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';
import { STATIC_ICON_REGISTRY, type IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { DEFAULT_ICON_SIZE, DEFAULT_ICON_STROKE, ICON_DEFAULTS, MISSING_ICON_GLYPH } from '@core/ui/icons/iconservice/constants.ts';
import type { IconAttributes, IconDefaultOptions, IconOptions, NormalizedIconOptions } from '@core/ui/icons/iconservice/types.ts';

const isIconName = (value: string | null): value is IconName => value !== null && value.length > 0 && hasOwn(STATIC_ICON_REGISTRY, value);

const listAllIconNames = (): IconName[] => {
    const names: IconName[] = [];
    for (const key of Object.keys(STATIC_ICON_REGISTRY)) {
        if (isIconName(key)) {
            names.push(key);
        }
    }
    return names;
};

const isDevBuild = (): boolean => Boolean(import.meta.env?.DEV);

const normalizeNumber = (value: number | undefined): number | null => {
    if (value === undefined) {
        return null;
    }
    const count = Number(value);
    if (!Number.isFinite(count) || count <= 0) {
        return null;
    }
    return count;
};

const normalizeString = (value: string | undefined): string | null => {
    const trimmed = value?.trim() ?? '';
    return trimmed ? trimmed : null;
};

const normalizeOptions = (options: IconOptions | undefined): NormalizedIconOptions => {
    if (!options || typeof options !== 'object') {
        return {
            size: null,
            width: null,
            height: null,
            strokeWidth: null,
            fill: null,
            stroke: null,
            className: null
        };
    }
    return {
        size: normalizeNumber(options.size),
        width: normalizeNumber(options.width),
        height: normalizeNumber(options.height),
        strokeWidth: normalizeNumber(options.strokeWidth),
        fill: normalizeString(options.fill),
        stroke: normalizeString(options.stroke),
        className: normalizeString(options.className)
    };
};

const resolveIconDefaults = (name: IconName): IconDefaultOptions => {
    const config = ICON_DEFAULTS[name];
    return {
        size: config?.size ?? DEFAULT_ICON_SIZE,
        strokeWidth: config?.strokeWidth ?? DEFAULT_ICON_STROKE
    };
};

const mergeDefaultIconOptions = (name: IconName, options: IconOptions | undefined): NormalizedIconOptions => {
    const base = normalizeOptions(options);
    const defaults = resolveIconDefaults(name);
    const size = base.size ?? defaults.size;
    const strokeWidth = base.strokeWidth ?? defaults.strokeWidth;
    return {
        ...base,
        size,
        strokeWidth
    };
};

const variantKey = (name: IconName, options: NormalizedIconOptions): string => `${name}:${options.size ?? ''}:${options.width ?? ''}:${options.height ?? ''}:${options.strokeWidth ?? ''}:${options.fill ?? ''}:${options.stroke ?? ''}:${options.className ?? ''}`;

const applySvgOptions = (svgContent: string, options: NormalizedIconOptions): string => {
    const trimmed = svgContent.trim();
    if (!trimmed) {
        return '';
    }
    const fragment = dom.createFragment(toTrustedSvg(trimmed));
    const first = fragment.firstElementChild;
    if (!isInstanceOf(first, SVGElement)) {
        return trimmed;
    }

    dom.addClass(first, 'ui-icon');
    if (options.className) {
        dom.addClass(first, options.className.split(/\s+/).filter(Boolean));
    }

    const size = options.size;
    const width = options.width ?? size;
    const height = options.height ?? size;

    if (!isNullOrUndefined(width)) {
        dom.setAttribute(first, 'width', String(width));
    }
    if (!isNullOrUndefined(height)) {
        dom.setAttribute(first, 'height', String(height));
    }
    if (!isNullOrUndefined(options.strokeWidth)) {
        dom.setAttribute(first, 'stroke-width', String(options.strokeWidth));
    }
    if (options.fill) {
        dom.setAttribute(first, 'fill', options.fill);
    }
    if (options.stroke) {
        dom.setAttribute(first, 'stroke', options.stroke);
    }

    return serializeElementToHtml(first);
};

const applySvgAttributes = (svgContent: string, attrs: IconAttributes): string => {
    if (!svgContent) {
        return svgContent;
    }
    const keys = Object.keys(attrs);
    if (!keys.length) {
        return svgContent;
    }
    const fragment = dom.createFragment(toTrustedSvg(svgContent));
    const element = fragment.firstElementChild;
    if (!element) {
        return svgContent;
    }
    for (const key of keys) {
        const value = attrs[key];
        if (isNullOrUndefined(value)) {
            continue;
        }
        dom.setAttribute(element, key, String(value));
    }
    return serializeElementToHtml(element);
};

const renderMissingIcon = (name: string, options: NormalizedIconOptions): string => {
    const base = applySvgOptions(MISSING_ICON_GLYPH, options);
    const attrs: IconAttributes = {
        'data-icon-missing': 'true',
        'data-icon-name': name
    };
    return applySvgAttributes(base, attrs);
};

export { applySvgAttributes, applySvgOptions, isDevBuild, isIconName, listAllIconNames, mergeDefaultIconOptions, normalizeOptions, renderMissingIcon, variantKey };
