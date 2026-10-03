/* SoAI - Charts feature chart component statics [frontend/assets/ts/features/charts/component/chartComponentStatics.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isArray, isFunction, isNullOrUndefined, isObject, hasOwn } from '@core/typeGuards.ts';
import type { ChartThemeManagedPaletteInput, ColorPalette } from '@features/charts/chartTypes.ts';

const CHART_EVENT_NAMES = new Set(['timeRangeChange', 'datapointHover']);
const SUPPORTED_CHART_TYPES = new Set(['area', 'bar', 'candlestick', 'heikin-ashi', 'spline', 'deviation', 'precision-line']);
const INTERACTION_BOOLEAN_OPTIONS = new Set(['enableCrosshair', 'enableMagnetMode', 'enableSmoothZoom', 'enableXAxisZoom', 'showAxisCoordinates', 'showDelta', 'showLegendTimestamp']);

type ChartThemeColorKey = 'primary' | 'secondary' | 'tertiary' | 'quaternary' | 'grid' | 'crosshair' | 'text' | 'textSecondary' | 'statusGreen' | 'statusYellow' | 'statusRed' | 'background';

const DEFAULT_CHART_COLORS: ColorPalette = Object.freeze({
    primary: '#4ade80',
    secondary: '#3b82f6',
    tertiary: '#f59e0b',
    quaternary: '#ec4899',
    grid: null,
    crosshair: 'rgba(128,128,128,0.6)',
    text: '#ffffff',
    textSecondary: 'rgba(255,255,255,0.6)',
    statusGreen: '#10b981',
    statusYellow: '#f59e0b',
    statusRed: '#ef4444',
    background: 'rgba(15, 23, 42, 0.88)'
});

const CSS_COLOR_VAR_MAP: Readonly<Record<ChartThemeColorKey, string[]>> = Object.freeze({
    primary: ['--accent-green'],
    secondary: ['--accent-blue'],
    tertiary: ['--accent-yellow'],
    quaternary: ['--accent-pink'],
    grid: ['--border-color', '--glass-border-strong'],
    crosshair: ['--text-tertiary'],
    text: ['--text-primary'],
    textSecondary: ['--text-secondary'],
    statusGreen: ['--accent-green'],
    statusYellow: ['--status-orange'],
    statusRed: ['--accent-red'],
    background: ['--surface-chart', '--bg-primary', '--surface-card', '--glass-surface-strong', '--bg-secondary']
});

const THEME_DEPENDENT_COLOR_KEYS: readonly ChartThemeColorKey[] = Object.freeze(['primary', 'secondary', 'tertiary', 'quaternary', 'grid', 'crosshair', 'text', 'textSecondary', 'statusGreen', 'statusYellow', 'statusRed', 'background']);

const DEFAULT_MAX_DATA_POINTS = 5e4;
const MAX_DATA_POINTS_HARD_LIMIT = 5e5;
const TIMESTAMP_EPSILON = 1e-3;
const DEFAULT_MIN_HEIGHT = 315;
const DEFAULT_VERTICAL_SCALE_PADDING_RATIO = 0.05;
const MIN_VERTICAL_PIXEL_PADDING = 14;
const DEFAULT_BOTTOM_AXIS_PADDING = 40;
const SECOND_MS = 1000;
const MINUTE_MS = 60000;
const HOUR_MS = 3600000;
const DAY_MS = 86400000;
const WEEK_MS = 604800000;
const YEAR_MS = 31536000000;
const MAX_DATE_FORMATTER_CACHE_SIZE = 128;

const dateTimeFormatterCache = new Map<string, Intl.DateTimeFormat | null>();

const isFin = Number.isFinite;

const normalizeCacheValue = (value: string | number | boolean | undefined | null): string => {
    if (value === undefined) return 'undefined';
    if (value === null) return 'null';
    return String(value);
};

const buildFormatterCacheKey = (options: Intl.DateTimeFormatOptions): string => {
    return [
        `calendar:${normalizeCacheValue(options.calendar)}`,
        `day:${normalizeCacheValue(options.day)}`,
        `dayPeriod:${normalizeCacheValue(options.dayPeriod)}`,
        `dateStyle:${normalizeCacheValue(options.dateStyle)}`,
        `era:${normalizeCacheValue(options.era)}`,
        `formatMatcher:${normalizeCacheValue(options.formatMatcher)}`,
        `fractionalSecondDigits:${normalizeCacheValue(options.fractionalSecondDigits)}`,
        `hour:${normalizeCacheValue(options.hour)}`,
        `hour12:${normalizeCacheValue(options.hour12)}`,
        `hourCycle:${normalizeCacheValue(options.hourCycle)}`,
        `localeMatcher:${normalizeCacheValue(options.localeMatcher)}`,
        `minute:${normalizeCacheValue(options.minute)}`,
        `month:${normalizeCacheValue(options.month)}`,
        `numberingSystem:${normalizeCacheValue(options.numberingSystem)}`,
        `second:${normalizeCacheValue(options.second)}`,
        `timeStyle:${normalizeCacheValue(options.timeStyle)}`,
        `timeZone:${normalizeCacheValue(options.timeZone)}`,
        `timeZoneName:${normalizeCacheValue(options.timeZoneName)}`,
        `weekday:${normalizeCacheValue(options.weekday)}`,
        `year:${normalizeCacheValue(options.year)}`
    ].join('|');
};

const registerFormatterInCache = (key: string, fileValue: Intl.DateTimeFormat | null): void => {
    if (dateTimeFormatterCache.has(key)) return;
    dateTimeFormatterCache.set(key, fileValue);
    if (dateTimeFormatterCache.size > MAX_DATE_FORMATTER_CACHE_SIZE) dateTimeFormatterCache.clear();
};

const normalizeNumberStr = (currentTime: string | null | undefined): number | null => {
    const value = String(currentTime).trim();
    const count = parseFloat(value);
    return value !== '' && isFin(count) ? (value.endsWith('%') ? count / 100 : count) : null;
};

const normalizeRgb = (currentTime: string | null | undefined): number | null => {
    const count = normalizeNumberStr(currentTime);
    return count !== null ? clampNumber(Math.round(String(currentTime).endsWith('%') ? count * 255 : count), 0, 255) : null;
};

const normalizeAlpha = (currentTime: string | null | undefined): number => {
    if (isNullOrUndefined(currentTime)) return 1;
    const count = normalizeNumberStr(currentTime);
    return count !== null ? clampNumber(count, 0, 1) : 1;
};

const normalizeHue = (currentTime: string | null | undefined): number | null => {
    const value = String(currentTime).trim().toLowerCase();
    if (!value) return null;
    const count = parseFloat(value);
    return value.endsWith('rad') ? count * (180 / Math.PI) : value.endsWith('turn') ? count * 360 : value.endsWith('grad') ? count * 0.9 : count;
};

const normalizePercent = (currentTime: string | null | undefined): number | null => {
    const count = normalizeNumberStr(currentTime);
    return count !== null ? clampNumber(count, 0, 1) : null;
};

const tryReadCssVariable = (src: CSSStyleDeclaration[], ids: string | string[]): string => {
    for (const stringValue of src) {
        for (const candidateValue of isArray(ids) ? ids : [ids]) {
            const value = stringValue.getPropertyValue(candidateValue)?.trim();
            if (value) return value;
        }
    }
    return '';
};

const getStyleSourcesForElement = (element: HTMLElement): CSSStyleDeclaration[] => {
    if (!element) {
        throw new Error('getStyleSourcesForElement requires an element');
    }
    const doc = element.ownerDocument;
    const win = doc.defaultView;
    if (!win || !isFunction(win.getComputedStyle)) {
        throw new Error('getStyleSourcesForElement requires window.getComputedStyle');
    }
    const currentTime = element.parentElement || doc.documentElement;
    const styles: CSSStyleDeclaration[] = [win.getComputedStyle(element)];
    if (currentTime !== element) {
        styles.push(win.getComputedStyle(currentTime));
    }
    if (currentTime !== doc.documentElement) {
        styles.push(win.getComputedStyle(doc.documentElement));
    }
    return styles;
};

const isTransparentColor = (candidateValue: string | null | undefined): boolean => {
    const count = String(candidateValue).trim().toLowerCase();
    if (!count || ['transparent', 'inherit', 'initial', 'unset', 'none'].includes(count)) return true;
    const match = count.match(/rgba\((?:\s*\d+\s*,){3}\s*([^)]+)\)/i);
    return match ? parseFloat(match[1] ?? '0') <= 0 : false;
};

const hasPaletteMetadata = (value: ChartThemeManagedPaletteInput | null | undefined): value is ChartThemeManagedPaletteInput => isObject(value) && hasOwn(value, '__themeManaged');

export { CHART_EVENT_NAMES, SUPPORTED_CHART_TYPES, INTERACTION_BOOLEAN_OPTIONS, DEFAULT_CHART_COLORS, CSS_COLOR_VAR_MAP, THEME_DEPENDENT_COLOR_KEYS, DEFAULT_MAX_DATA_POINTS, MAX_DATA_POINTS_HARD_LIMIT, TIMESTAMP_EPSILON, DEFAULT_MIN_HEIGHT, DEFAULT_VERTICAL_SCALE_PADDING_RATIO, MIN_VERTICAL_PIXEL_PADDING, DEFAULT_BOTTOM_AXIS_PADDING, SECOND_MS, MINUTE_MS, HOUR_MS, DAY_MS, WEEK_MS, YEAR_MS, dateTimeFormatterCache, MAX_DATE_FORMATTER_CACHE_SIZE, isFin, buildFormatterCacheKey, registerFormatterInCache, normalizeNumberStr, normalizeRgb, normalizeAlpha, normalizeHue, normalizePercent, tryReadCssVariable, getStyleSourcesForElement, isTransparentColor, hasPaletteMetadata };
