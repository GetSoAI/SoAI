/* SoAI - Charts feature primitives [frontend/assets/ts/features/charts/rendering/primitives.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ColorPalette, ThemeStyles } from '@features/charts/chartTypes.ts';
import type { CornerRadii } from '@features/charts/rendering/renderingModels.ts';

const { max } = Math;

const DEFAULT_CORNER_RADIUS = 10;

const getChartCornerRadii = (element: HTMLElement): CornerRadii => {
    const fallback = DEFAULT_CORNER_RADIUS;
    const resolveRadius = (value: string): number => {
        if (!value) return Number.NaN;
        const match = String(value).match(/-?\d*\.?\d+/);
        if (!match) return Number.NaN;
        const numeric = Number.parseFloat(match[0]);
        return Number.isFinite(numeric) ? max(0, numeric) : Number.NaN;
    };
    const win = element.ownerDocument.defaultView;
    if (!win || typeof win.getComputedStyle !== 'function') {
        throw new Error('Chart rendering requires window.getComputedStyle');
    }
    const style = win.getComputedStyle(element);
    const tl = resolveRadius(style.borderTopLeftRadius || style.getPropertyValue('border-top-left-radius'));
    const tr = resolveRadius(style.borderTopRightRadius || style.getPropertyValue('border-top-right-radius'));
    const br = resolveRadius(style.borderBottomRightRadius || style.getPropertyValue('border-bottom-right-radius'));
    const bl = resolveRadius(style.borderBottomLeftRadius || style.getPropertyValue('border-bottom-left-radius'));
    const use = (value: number): number => (Number.isNaN(value) ? fallback : value);
    return { tl: use(tl), tr: use(tr), br: use(br), bl: use(bl) };
};

const getChartCornerRadius = (element: HTMLElement): number => {
    const { tl, tr, br, bl } = getChartCornerRadii(element);
    return max(tl, tr, br, bl);
};

const drawRoundedRect = (context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, xCoordinate: number, yCoordinate: number, width: number, height: number, radius: number | CornerRadii): void => {
    const radii =
        radius && typeof radius === 'object'
            ? {
                  tl: max(0, Number(radius.tl) || 0),
                  tr: max(0, Number(radius.tr) || 0),
                  br: max(0, Number(radius.br) || 0),
                  bl: max(0, Number(radius.bl) || 0)
              }
            : {
                  tl: max(0, Number(radius) || 0),
                  tr: max(0, Number(radius) || 0),
                  br: max(0, Number(radius) || 0),
                  bl: max(0, Number(radius) || 0)
              };
    const { tl, tr, br, bl } = radii;
    context.beginPath();
    context.moveTo(xCoordinate + tl, yCoordinate);
    context.lineTo(xCoordinate + width - tr, yCoordinate);
    if (tr > 0) context.arcTo(xCoordinate + width, yCoordinate, xCoordinate + width, yCoordinate + tr, tr);
    else context.lineTo(xCoordinate + width, yCoordinate);
    context.lineTo(xCoordinate + width, yCoordinate + height - br);
    if (br > 0) context.arcTo(xCoordinate + width, yCoordinate + height, xCoordinate + width - br, yCoordinate + height, br);
    else context.lineTo(xCoordinate + width, yCoordinate + height);
    context.lineTo(xCoordinate + bl, yCoordinate + height);
    if (bl > 0) context.arcTo(xCoordinate, yCoordinate + height, xCoordinate, yCoordinate + height - bl, bl);
    else context.lineTo(xCoordinate, yCoordinate + height);
    context.lineTo(xCoordinate, yCoordinate + tl);
    if (tl > 0) context.arcTo(xCoordinate, yCoordinate, xCoordinate + tl, yCoordinate, tl);
    else context.lineTo(xCoordinate, yCoordinate);
    context.closePath();
};

const drawCoordinateLabel = (context: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D, xCoordinate: number, yCoordinate: number, text: string, options: { bgColor: string; textColor: string; font?: string; paddingX?: number; paddingY?: number; radius?: number }): void => {
    const { bgColor, textColor, font = '600 12px sans-serif', paddingX = 8, paddingY = 4, radius = 4 } = options;
    context.save();
    context.font = font;
    const metrics = context.measureText(text);
    const fontSize = parseInt(font.match(/(\d+)px/)?.[1] || font.match(/\d+/)?.[0] || '12', 10);
    const boxW = metrics.width + paddingX * 2;
    const boxH = fontSize + paddingY * 2;

    context.fillStyle = bgColor;
    drawRoundedRect(context, xCoordinate - boxW / 2, yCoordinate - boxH / 2, boxW, boxH, radius);
    context.fill();

    Object.assign(context, {
        fillStyle: textColor,
        textAlign: 'center',
        textBaseline: 'middle'
    });
    context.fillText(text, xCoordinate, yCoordinate);
    context.restore();
};

type ThemeColorKey = keyof ColorPalette | keyof ThemeStyles;

const readThemeStyleColor = (themeStyles: ThemeStyles | null, key: ThemeColorKey): string | boolean | null | undefined => {
    if (!themeStyles) return undefined;
    switch (key) {
        case 'isDark':
            return themeStyles.isDark;
        case 'background':
            return themeStyles.background;
        case 'plotBackground':
            return themeStyles.plotBackground;
        case 'tooltipBackground':
            return themeStyles.tooltipBackground;
        case 'tooltipTextColor':
            return themeStyles.tooltipTextColor;
        case 'legendBackground':
            return themeStyles.legendBackground;
        case 'legendTextColor':
            return themeStyles.legendTextColor;
        case 'legendBorderColor':
            return themeStyles.legendBorderColor;
        case 'crosshairValueBackground':
            return themeStyles.crosshairValueBackground;
        case 'crosshairValueTextColor':
            return themeStyles.crosshairValueTextColor;
        case 'axisGuideColor':
            return themeStyles.axisGuideColor;
        case 'candlestickUpColor':
            return themeStyles.candlestickUpColor;
        case 'candlestickDownColor':
            return themeStyles.candlestickDownColor;
        default:
            return undefined;
    }
};

const resolveThemeColor = (themeStyles: ThemeStyles | null, colorPalette: ColorPalette, keys: readonly ThemeColorKey[]): string => {
    for (const key of keys) {
        const value = readThemeStyleColor(themeStyles, key) || colorPalette[key];
        if (typeof value === 'string' && value.length > 0) return value;
    }
    return '';
};

const requireThemeColor = (themeStyles: ThemeStyles | null, key: keyof ThemeStyles): string => {
    const value = readThemeStyleColor(themeStyles, key);
    if (isString(value) && value.trim().length > 0) {
        return value;
    }
    throw new Error(`Chart theme requires ${key}`);
};

const hexToRgba = (hexColor: string, alpha: number = 1): string => {
    if (!isString(hexColor) || !hexColor.length) return `rgba(0,0,0,${alpha})`;
    if (hexColor.startsWith('rg')) {
        const match = hexColor.match(/rgba?\(([^)]+)\)/i);
        const channels = match?.[1]?.replace(/[,/]/g, ' ').trim().split(/\s+/).slice(0, 3);
        if (channels?.length === 3) return `rgba(${channels[0]},${channels[1]},${channels[2]},${alpha})`;
        return hexColor.startsWith('rgba') ? hexColor : hexColor.replace(')', `,${alpha})`).replace('rgb', 'rgba');
    }
    const value = hexColor.slice(1);
    let redChannel = 0;
    let greenChannel = 0;
    let secondValue = 0;
    if (value.length === 3) {
        redChannel = parseInt(value.charAt(0) + value.charAt(0), 16);
        greenChannel = parseInt(value.charAt(1) + value.charAt(1), 16);
        secondValue = parseInt(value.charAt(2) + value.charAt(2), 16);
    } else if (value.length === 6) {
        const count = parseInt(value, 16);
        redChannel = (count >> 16) & 255;
        greenChannel = (count >> 8) & 255;
        secondValue = count & 255;
    } else return `rgba(0,0,0,${alpha})`;
    return `rgba(${redChannel},${greenChannel},${secondValue},${alpha})`;
};

export { getChartCornerRadii, getChartCornerRadius, drawRoundedRect, drawCoordinateLabel, resolveThemeColor, requireThemeColor, hexToRgba };
