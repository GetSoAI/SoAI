/* SoAI - Charts feature state service [frontend/assets/ts/features/charts/component/state/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { getMatchMedia } from '@core/environment/public.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isBoolean, isNullOrUndefined, isObject, isPlainObject, isString, isArray, hasOwn } from '@core/typeGuards.ts';
import { resolveChartColor, type ChartColorMode } from '@core/ui/chartColors.ts';
import type { ChartColorInput, ChartThemeFlagInput, ChartThemeManagedPaletteInput, ColorPalette, ThemeStyles } from '@features/charts/chartTypes.ts';
import { calculateContrast, calculateLuminance, normalizeBackgroundColor, parseColorComponents } from '@features/charts/component/chartColorAnalysis.ts';
import { DEFAULT_CHART_COLORS, CSS_COLOR_VAR_MAP, isFin, THEME_DEPENDENT_COLOR_KEYS } from '@features/charts/component/chartComponentStatics.ts';
import type { ThemeColorFlags } from '@features/charts/component/chartComponentTypes.ts';
import { logDebug, logError } from '@features/charts/component/logger.ts';
import { getStyleSources, readCssVariable } from '@features/charts/component/state/adapters.ts';
import type { DynamicPrimaryColorHost } from '@features/charts/component/state/types.ts';
import { requireChartStorageService } from '@features/charts/component/state/guards.ts';

const parseChartColorMode = (value: string | null | undefined): ChartColorMode => {
    const normalizedValue = String(value).trim().toLowerCase();
    if (normalizedValue === 'disabled' || normalizedValue === 'static' || normalizedValue === 'dynamic') return normalizedValue;
    return 'dynamic';
};

const sanitizeThemeFlags = (flagInput: ChartThemeFlagInput | null | undefined = {}): ThemeColorFlags => {
    const source = isPlainObject(flagInput) ? flagInput : {};
    const response: ThemeColorFlags = {};
    THEME_DEPENDENT_COLOR_KEYS.forEach((key) => {
        response[key] = source[key] === true;
    });
    return response;
};

const separatePaletteMetadata = (paletteInput: ChartThemeManagedPaletteInput | null | undefined): { palette: ColorPalette; meta: ThemeColorFlags | null } => {
    if (!isPlainObject(paletteInput)) return { palette: {}, meta: null };

    const themeManaged = paletteInput['__themeManaged'];
    const meta = (() => {
        if (isPlainObject(themeManaged)) {
            return sanitizeThemeFlags(themeManaged);
        }
        const themeManagedText = typeof themeManaged === 'string' ? themeManaged : '';
        if (themeManagedText.trim()) {
            try {
                const parsed = parseRequiredJsonText(themeManagedText);
                if (isPlainObject(parsed)) {
                    return sanitizeThemeFlags(parsed);
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                logDebug('Failed to parse chart theme metadata overrides', runtimeError);
            }
        }
        return null;
    })();

    const palette: ColorPalette = {};
    for (const [key, value] of Object.entries(paletteInput)) {
        if (key === '__themeManaged') continue;
        if (isString(value)) palette[key] = value;
    }
    return { palette, meta };
};

const resolvePaletteFromCssAndOverrides = (element: HTMLElement, src: ColorPalette | undefined): { palette: ColorPalette; flags: ThemeColorFlags } => {
    const styles = getStyleSources(element);
    const pal: ColorPalette = {};
    const flg: Record<string, boolean> = {};
    Object.entries(CSS_COLOR_VAR_MAP).forEach(([key, index]) => {
        const value = readCssVariable(styles, index);
        if (value) {
            pal[key] = value;
            flg[key] = true;
        }
    });
    const { palette: ovr, meta } = separatePaletteMetadata(src);
    Object.entries(ovr).forEach(([key, value]) => {
        if (isNullOrUndefined(value)) return;
        pal[key] = value;
        if (meta && hasOwn(meta, key)) flg[key] = meta[key] === true;
        else if (!hasOwn(flg, key)) flg[key] = false;
    });
    return { palette: pal, flags: sanitizeThemeFlags(flg) };
};

const deriveThemeFlags = (current: ThemeColorFlags, meta: ThemeColorFlags | null, ovr: ColorPalette): ThemeColorFlags => {
    if (meta) return sanitizeThemeFlags(meta);
    const cur: ThemeColorFlags = { ...(current || sanitizeThemeFlags()) };
    if (isObject(ovr))
        THEME_DEPENDENT_COLOR_KEYS.forEach((key) => {
            if (hasOwn(ovr, key)) cur[key] = false;
            else if (!hasOwn(cur, key)) cur[key] = false;
        });
    return sanitizeThemeFlags(cur);
};

const normalizeColorParserInput = (value: ChartColorInput): Parameters<typeof parseColorComponents>[0] => {
    if (isNullOrUndefined(value)) return undefined;
    if (isObject(value) || isString(value)) return value;
    return String(value);
};

const inferIsDarkFromPalette = (point: ChartThemeManagedPaletteInput | null | undefined): boolean | null => {
    if (!isPlainObject(point)) return null;
    const textComponents = parseColorComponents(normalizeColorParserInput(point['text']));
    const bgComponents = parseColorComponents(normalizeColorParserInput(point['background']));
    const textL = textComponents ? calculateLuminance(textComponents) : null;
    const bgL = bgComponents ? calculateLuminance(bgComponents) : null;
    const textNumber = textL !== null && isFin(textL) ? textL : null;
    const bgNumber = bgL !== null && isFin(bgL) ? bgL : null;
    if (textNumber !== null && bgNumber !== null) return textNumber > bgNumber;
    if (textNumber !== null) return textNumber > 0.45;
    if (bgNumber !== null) return bgNumber < 0.35;
    return null;
};

const normalizeColorPalette = (element: HTMLElement, paletteInput: ChartThemeManagedPaletteInput | null | undefined): ColorPalette => {
    const base: ColorPalette = { ...DEFAULT_CHART_COLORS };
    if (!isObject(paletteInput) || isArray(paletteInput)) return base;
    const palette: ColorPalette = { ...base };
    for (const [key, value] of Object.entries(paletteInput)) {
        if (key === '__themeManaged') {
            continue;
        }
        if (value === undefined) {
            palette[key] = undefined;
            continue;
        }
        if (value === null || typeof value === 'string') {
            palette[key] = value;
            continue;
        }
        throw new Error(`Color palette entries must be string|null|undefined: ${key}`);
    }
    const inferredDark = inferIsDarkFromPalette(palette);
    const isDark = isBoolean(inferredDark) ? inferredDark : isDarkTheme(element, palette);
    palette['background'] = normalizeBackgroundColor(palette['background'], isDark, parseColorComponents);
    return palette;
};

const mergeColorPalette = (element: HTMLElement, paletteOverride: ColorPalette): ColorPalette => {
    const match: ColorPalette = { ...DEFAULT_CHART_COLORS, ...paletteOverride };
    for (const key in match) {
        if (key === '__themeManaged') {
            delete match[key];
            continue;
        }
        if (isNullOrUndefined(match[key])) delete match[key];
    }
    return normalizeColorPalette(element, match);
};

const applyAlphaToColor = (colorInput: ChartColorInput, alphaInput: number | string | null | undefined, fallbackColor: string | null = null): string => {
    const colorComponents = parseColorComponents(normalizeColorParserInput(colorInput));
    const alpha = clampNumber(Number(alphaInput), 0, 1);
    return colorComponents ? `rgba(${colorComponents.red}, ${colorComponents.green}, ${colorComponents.blue}, ${alpha})` : (fallbackColor ?? `rgba(0, 0, 0, ${alpha})`);
};

const resolveThemeStyle = (styles: ReadonlyArray<CSSStyleDeclaration>, cssVariables: string | string[], fallback: string | null | undefined): string => {
    const fallbackValue = fallback == null ? '' : String(fallback);
    const value = readCssVariable(styles, cssVariables);
    if (!value) return fallbackValue;
    const normalized = value.trim().toLowerCase();
    return normalized && normalized !== 'transparent' && normalized !== 'inherit' && normalized !== 'initial' && normalized !== 'unset' && normalized !== 'none' ? value : fallbackValue;
};

const requireThemeStyle = (styles: ReadonlyArray<CSSStyleDeclaration>, cssVar: string): string => {
    const value = readCssVariable(styles, cssVar);
    const normalized = value.trim().toLowerCase();
    if (!normalized || normalized === 'transparent' || normalized === 'inherit' || normalized === 'initial' || normalized === 'unset' || normalized === 'none') {
        throw new Error(`Chart theme requires ${cssVar}`);
    }
    return value;
};

const getReadableTextColor = (chartColors: ColorPalette, bg: ChartColorInput, isDarkThemeValue: boolean, lightText: string, darkText: string): string => {
    const base = parseColorComponents(normalizeColorParserInput(bg));
    if (!base) return isDarkThemeValue ? darkText : lightText;
    let { red: redChannel, green: greenChannel, blue: blueChannel, alpha } = base;
    if (alpha < 1) {
        const under = parseColorComponents(normalizeColorParserInput(chartColors.background)) || {
            red: isDarkThemeValue ? 15 : 255,
            green: isDarkThemeValue ? 23 : 255,
            blue: isDarkThemeValue ? 42 : 255,
            alpha: 1
        };
        redChannel = Math.round(redChannel * alpha + under.red * (1 - alpha));
        greenChannel = Math.round(greenChannel * alpha + under.green * (1 - alpha));
        blueChannel = Math.round(blueChannel * alpha + under.blue * (1 - alpha));
    }
    const backgroundLuminance = calculateLuminance({ red: redChannel, green: greenChannel, blue: blueChannel, alpha: 1 });
    const lightComponents = parseColorComponents(lightText);
    const darkComponents = parseColorComponents(darkText);
    const lightLuminance = lightComponents ? calculateLuminance(lightComponents) : 1;
    const darkLuminance = darkComponents ? calculateLuminance(darkComponents) : 0;
    const lightContrast = calculateContrast(backgroundLuminance, lightLuminance) ?? 0;
    const darkContrast = calculateContrast(backgroundLuminance, darkLuminance) ?? 0;
    return lightContrast >= darkContrast ? lightText : darkText;
};

const isDarkTheme = (element: HTMLElement, palette: ColorPalette): boolean => {
    const inf = inferIsDarkFromPalette(palette);
    if (isBoolean(inf)) return inf;
    const doc = element.ownerDocument;
    if (doc.documentElement?.classList.contains('theme-dark') || doc.body?.classList.contains('theme-dark')) return true;
    if (doc.documentElement?.classList.contains('theme-light') || doc.body?.classList.contains('theme-light')) return false;
    try {
        const matchMedia = getMatchMedia();
        const query = matchMedia('(prefers-color-scheme: dark)');
        return query.matches;
    } catch (error) {
        const runtimeError = ensureError(error);
        logError('Reading system color scheme failed', runtimeError);
        throw ensureError(error);
    }
};

const getThemeStyles = (element: HTMLElement, colors: ColorPalette): ThemeStyles => {
    const isDark = isDarkTheme(element, colors);
    const styles = getStyleSources(element);
    const resolvedTextPrimary = resolveThemeStyle(styles, '--text-primary', colors.text || colors.textSecondary || colors.text || colors.background);
    const resolvedTextSecondary = resolveThemeStyle(styles, '--text-secondary', colors.textSecondary || resolvedTextPrimary || colors.text || colors.background);
    const bg = resolveThemeStyle(styles, ['--surface-chart', '--bg-primary', '--surface-card', '--glass-surface-strong', '--bg-secondary'], normalizeBackgroundColor(colors.background, isDark, parseColorComponents));
    const plotBackground = resolveThemeStyle(styles, '--chart-plot-background', bg);
    const tbg = resolveThemeStyle(styles, ['--glass-surface-overlay-strong', '--surface-card', '--surface-chart'], bg);
    const lbg = resolveThemeStyle(styles, ['--glass-surface-overlay', '--surface-card', '--surface-chart'], bg);
    const axisGuide = resolveThemeStyle(styles, ['--border-color', '--glass-border-strong', '--surface-card-border'], colors.textSecondary || colors.text || colors.background || bg);
    const crosshairBg = requireThemeStyle(styles, '--chart-coordinate-label-bg');
    const crosshairText = requireThemeStyle(styles, '--chart-coordinate-label-color');
    const candlestickUpColor = resolveThemeStyle(styles, '--chart-candlestick-up', '');
    const candlestickDownColor = resolveThemeStyle(styles, '--chart-candlestick-down', '');
    const tooltipTextColor = getReadableTextColor(colors, tbg, isDark, resolvedTextPrimary, resolvedTextSecondary);
    const legendTextColor = getReadableTextColor(colors, lbg, isDark, resolvedTextPrimary, resolvedTextSecondary);

    return {
        isDark,
        background: bg,
        plotBackground,
        tooltipBackground: tbg,
        tooltipTextColor,
        legendBackground: lbg,
        legendTextColor,
        legendBorderColor: applyAlphaToColor(axisGuide, isDark ? 0.42 : 0.22),
        crosshairValueBackground: crosshairBg,
        crosshairValueTextColor: crosshairText,
        axisGuideColor: axisGuide,
        candlestickUpColor,
        candlestickDownColor
    };
};

const resolveDynamicPrimaryColor = (chart: DynamicPrimaryColorHost): string | null => {
    const context = chart.chartOptions.chartColorContext;
    if (!context) return null;
    const storage = requireChartStorageService();
    return resolveChartColor(parseChartColorMode(storage.getChartColorMode()), storage.getChartStaticColor(), context.device, context.deviceIndex, context.metric, context.metricIndex, context['subjectName']);
};

export { applyAlphaToColor, isDarkTheme, deriveThemeFlags, getThemeStyles, normalizeColorPalette, mergeColorPalette, resolveDynamicPrimaryColor, resolvePaletteFromCssAndOverrides, sanitizeThemeFlags, separatePaletteMetadata };
