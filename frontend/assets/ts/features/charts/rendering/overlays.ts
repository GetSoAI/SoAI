/* SoAI - Charts feature overlays [frontend/assets/ts/features/charts/rendering/overlays.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasRtlScriptLetters, isolateLtrText } from '@core/localization/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { ChartOptions, ColorPalette, CrosshairState } from '@features/charts/chartTypes.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { drawCoordinateLabel, drawRoundedRect, requireThemeColor, resolveThemeColor } from '@features/charts/rendering/primitives.ts';
import { getChartTextStyle } from '@features/charts/rendering/textStyle.ts';

const { max, min, round } = Math;
const TOOLTIP_SECONDARY_ALPHA = 0.72;

const optionalFiniteNumber = (value: JsonValue | null | undefined): number | null => (isFiniteNumber(value) ? value : null);

const formatNumberDelta = (prefix: string, value: number, formatValue: (value: number) => string): string => `${prefix}${isolateLtrText(`${value >= 0 ? '+' : ''}${formatValue(value)}`)}`;

const getOhlcMetadata = (): { open: string; high: string; low: string; close: string } => ({
    open: i18n.t('charts.legend.openPrefix'),
    high: i18n.t('charts.legend.highPrefix'),
    low: i18n.t('charts.legend.lowPrefix'),
    close: i18n.t('charts.legend.closePrefix')
});

const isOhlcType = (scene: ChartRenderingScene, options: ChartOptions): boolean => scene.buffers.isOhlcRenderingType(options.chartType) ?? isOhlcChartType(options.chartType);

const drawTooltip = (scene: ChartRenderingScene, context: CanvasRenderingContext2D): void => {
    const crosshair: CrosshairState = scene.state.crosshair;
    const { x: xCoordinate, y: yCoordinate, value, timestamp, open, high, low, close, datasetValues, gap } = crosshair;
    const theme = scene.geometry.getThemeStyles();
    const options: ChartOptions = scene.state.chartOptions;
    const colors: ColorPalette = options.colors;
    const isCandle = isOhlcType(scene, options);
    const textStyle = getChartTextStyle(scene.state.element);

    const lines: { text: string; font?: string | undefined; color?: string | undefined; secondary?: boolean | undefined }[] = [];
    if (gap) {
        lines.push({ text: i18n.t('charts.legend.noDataLabel') });
    } else if (isCandle) {
        const meta = getOhlcMetadata();
        if (isFiniteNumber(open)) lines.push({ text: `${meta.open}${isolateLtrText(scene.format.formatValue(open))}` });
        if (isFiniteNumber(high)) lines.push({ text: `${meta.high}${isolateLtrText(scene.format.formatValue(high))}` });
        if (isFiniteNumber(low)) lines.push({ text: `${meta.low}${isolateLtrText(scene.format.formatValue(low))}` });
        const closeValue = isFiniteNumber(close) ? close : isFiniteNumber(value) ? value : null;
        if (closeValue !== null) lines.push({ text: `${meta.close}${isolateLtrText(scene.format.formatValue(closeValue))}` });
    } else if (isFiniteNumber(value)) {
        lines.push({ text: isolateLtrText(scene.format.formatValue(value)) });
    }

    if (isFiniteNumber(timestamp)) {
        lines.push({
            text: String(scene.format.formatDetailedTimestamp(timestamp, { includeSeconds: true, includeMilliseconds: (scene.geometry.getVisibleTimeSpan?.() ?? 0) <= 5000 })),
            font: `11px ${textStyle.fontFamily}`,
            secondary: true
        });
    }

    if (datasetValues && !gap) {
        const nameValueSeparator = i18n.t('charts.legend.nameValueSeparator');
        const dsCols = [colors['secondary'], colors['tertiary'], colors['quaternary'], colors['statusGreen'], colors['statusYellow'], colors['statusRed']].filter((item): item is string => Boolean(item));
        let colorIndex = 0;
        for (const [name, rawValue] of Object.entries(datasetValues)) {
            lines.push({
                text: `${name}${nameValueSeparator}${isolateLtrText(scene.format.formatValue(rawValue))}`,
                font: `11px ${textStyle.fontFamily}`,
                color: dsCols[colorIndex % dsCols.length]
            });
            colorIndex += 1;
        }
    }

    const tooltipBg = requireThemeColor(theme, 'crosshairValueBackground');
    const tooltipText = requireThemeColor(theme, 'crosshairValueTextColor');

    context.save();
    const baseAlpha = context.globalAlpha;
    context.font = `12px ${textStyle.fontFamily}`;
    context.direction = textStyle.direction;
    const lineHeight = 16;
    const maxWidth = lines.reduce((acc, line) => max(acc, context.measureText(line.text).width), 0);
    const boxPaddingX = 10;
    const boxPaddingY = 8;
    const boxWidth = maxWidth + boxPaddingX * 2;
    const boxHeight = lines.length * lineHeight + boxPaddingY * 2;
    const chartDims = scene.geometry.getChartDimensions();
    const boxX = xCoordinate + 12;
    const boxY = min(max(scene.state.padding.top, yCoordinate - boxHeight / 2), chartDims.top + chartDims.chartHeight - boxHeight);

    context.fillStyle = tooltipBg;
    drawRoundedRect(context, boxX, boxY, boxWidth, boxHeight, 6);
    context.fill();

    for (let index = 0; index < lines.length; index++) {
        const line = lines[index];
        if (!line) continue;
        context.font = line.font ?? `12px ${textStyle.fontFamily}`;
        context.direction = hasRtlScriptLetters(line.text) ? 'rtl' : 'ltr';
        context.fillStyle = line.color ?? tooltipText;
        context.globalAlpha = line.secondary ? baseAlpha * TOOLTIP_SECONDARY_ALPHA : baseAlpha;
        context.textAlign = textStyle.direction === 'rtl' ? 'right' : 'left';
        context.textBaseline = 'middle';
        context.fillText(line.text, textStyle.direction === 'rtl' ? boxX + boxWidth - boxPaddingX : boxX + boxPaddingX, boxY + boxPaddingY + lineHeight * (index + 0.5));
    }
    context.restore();
};

const drawCrosshair = (scene: ChartRenderingScene, context: CanvasRenderingContext2D): void => {
    const dims = scene.geometry.getChartDimensions();
    const crosshair: CrosshairState = scene.state.crosshair;
    const { x: xCoordinate, y: yCoordinate, value } = crosshair;
    const themeStyles = scene.geometry.getThemeStyles();
    const colors: ColorPalette = scene.state.chartOptions.colors;
    const baseCrosshair = resolveThemeColor(themeStyles, colors, ['crosshair', 'axisGuideColor', 'textSecondary', 'text', 'primary']);
    const crosshairColor = scene.geometry.applyAlphaToColor ? scene.geometry.applyAlphaToColor(baseCrosshair, themeStyles?.isDark ? 1 : 0.7) : baseCrosshair;

    context.save();
    context.setLineDash([5, 5]);
    context.strokeStyle = crosshairColor;
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(xCoordinate, dims.top);
    context.lineTo(xCoordinate, dims.top + dims.chartHeight);
    context.moveTo(dims.left, yCoordinate);
    context.lineTo(dims.right, yCoordinate);
    context.stroke();
    context.restore();

    if (!scene.state.chartOptions.showAxisCoordinates || !isFiniteNumber(value)) return;
    if (!crosshair.gap) {
        const label = isolateLtrText(scene.format.formatValue(value));
        context.save();
        context.font = '600 12px sans-serif';
        const labelWidth = context.measureText(label).width + 16;
        context.restore();
        const labelCenter = Math.max(labelWidth / 2 + 4, Math.min(dims.width - labelWidth / 2 - 4, dims.right + 4 + labelWidth / 2));
        drawCoordinateLabel(context, labelCenter, yCoordinate, label, {
            bgColor: requireThemeColor(themeStyles, 'crosshairValueBackground'),
            textColor: requireThemeColor(themeStyles, 'crosshairValueTextColor')
        });
    }
    drawTooltip(scene, context);
};

const drawLegend = (scene: ChartRenderingScene, context: CanvasRenderingContext2D): void => {
    const legend = scene.state.legendData;
    const { value, min: mn, max: mx, avg, baseline, delta, status, timestamp, open, high, low, close } = legend;
    const valueNumber = optionalFiniteNumber(value);
    const closeNumber = optionalFiniteNumber(close);
    if (valueNumber === null && closeNumber === null) return;

    const meta = getOhlcMetadata();
    const deltaPrefix = i18n.t('charts.legend.deltaPrefix');
    const minPrefix = i18n.t('charts.legend.minPrefix');
    const maxPrefix = i18n.t('charts.legend.maxPrefix');
    const baselinePrefix = i18n.t('charts.legend.baselinePrefix');
    const deviationPrefix = i18n.t('charts.legend.deviationPrefix');
    const avgPrefix = i18n.t('charts.legend.avgPrefix');
    const realtimeLabel = i18n.t('charts.legend.realtimeLabel');
    const secondsAgoSuffix = i18n.t('charts.legend.secondsAgoSuffix');
    const partSeparator = i18n.t('charts.legend.partSeparator');
    const metricNameSeparator = i18n.t('charts.legend.metricNameSeparator');
    const nameValueSeparator = i18n.t('charts.legend.nameValueSeparator');
    const statusMarker = i18n.t('charts.legend.statusMarker');
    const statusMarkerSpacing = i18n.t('charts.legend.statusMarkerSpacing');

    const parts: string[] = [];
    const span = scene.geometry.getVisibleTimeSpan?.() ?? 0;
    const crosshair: CrosshairState = scene.state.crosshair;
    const inGap = crosshair.visible && crosshair.gap;
    if (crosshair.visible && isFiniteNumber(crosshair.timestamp)) {
        parts.push(String(scene.format.formatDetailedTimestamp(crosshair.timestamp, { includeSeconds: span <= 90000 })));
    }

    const options: ChartOptions = scene.state.chartOptions;
    if (isOhlcType(scene, options)) {
        const openNumber = optionalFiniteNumber(open);
        const highNumber = optionalFiniteNumber(high);
        const lowNumber = optionalFiniteNumber(low);
        const closeValue = closeNumber ?? valueNumber;
        if (openNumber !== null) parts.push(`${meta.open}${isolateLtrText(scene.format.formatValue(openNumber))}`);
        if (highNumber !== null) parts.push(`${meta.high}${isolateLtrText(scene.format.formatValue(highNumber))}`);
        if (lowNumber !== null) parts.push(`${meta.low}${isolateLtrText(scene.format.formatValue(lowNumber))}`);
        if (closeValue !== null) parts.push(`${meta.close}${isolateLtrText(scene.format.formatValue(closeValue))}`);
    } else if (valueNumber !== null) {
        parts.push(inGap ? i18n.t('charts.legend.noDataLabel') : isolateLtrText(scene.format.formatValue(valueNumber)));
    }

    const deltaNumber = optionalFiniteNumber(delta);
    if (options.showDelta && deltaNumber !== null && !inGap) parts.push(formatNumberDelta(deltaPrefix, deltaNumber, (value) => scene.format.formatValue(value)));
    const minNumber = optionalFiniteNumber(mn);
    const maxNumber = optionalFiniteNumber(mx);
    if (minNumber !== null) parts.push(`${minPrefix}${isolateLtrText(scene.format.formatValue(minNumber))}`);
    if (maxNumber !== null) parts.push(`${maxPrefix}${isolateLtrText(scene.format.formatValue(maxNumber))}`);

    const baselineNumber = optionalFiniteNumber(baseline);
    if (options.chartType === 'deviation' && baselineNumber !== null) {
        parts.push(`${baselinePrefix}${isolateLtrText(scene.format.formatValue(baselineNumber))}`);
        if (valueNumber !== null) parts.push(formatNumberDelta(deviationPrefix, valueNumber - baselineNumber, (value) => scene.format.formatValue(value)));
    } else {
        const avgNumber = optionalFiniteNumber(avg);
        if (avgNumber !== null) parts.push(`${avgPrefix}${isolateLtrText(scene.format.formatValue(avgNumber))}`);
    }

    const datasetValues = crosshair.datasetValues;
    if (datasetValues && !inGap) {
        for (const [name, rawValue] of Object.entries(datasetValues)) parts.push(`${name}${nameValueSeparator}${isolateLtrText(scene.format.formatValue(rawValue))}`);
    }

    const timestampNumber = optionalFiniteNumber(timestamp);
    if (options.showLegendTimestamp && timestampNumber !== null) {
        const age = serverEpochMs() - timestampNumber;
        parts.push(age < 5000 ? realtimeLabel : age < 60000 ? `${isolateLtrText(String(round(age / 1000)))}${secondsAgoSuffix}` : String(scene.format.formatTimestamp(timestampNumber, 'full')));
    }

    const metricNamePrefix = options.metricName ? `${options.metricName}${metricNameSeparator}` : '';
    const textStyle = getChartTextStyle(scene.state.element);
    const chartDims = scene.geometry.getChartDimensions();
    const narrow = chartDims.width <= 600;
    const legendMaxWidth = max(1, chartDims.width - 8 - scene.state.padding.left);
    const startX = scene.state.padding.left;
    const endX = chartDims.width - 8;
    const rtl = textStyle.direction === 'rtl';
    const directionSign = rtl ? -1 : 1;
    const anchorX = rtl ? endX : startX;
    context.save();
    Object.assign(context, { font: `12px ${textStyle.fontFamily}`, direction: textStyle.direction, textAlign: rtl ? 'right' : 'left', textBaseline: 'top' });
    if (narrow) {
        const fullText = `${status ? statusMarkerSpacing : ''}${metricNamePrefix}${parts.join(partSeparator)}`;
        const fullWidth = context.measureText(fullText).width;
        const fontSize = max(9, min(11, Math.floor((12 * legendMaxWidth) / max(1, fullWidth))));
        context.font = `${fontSize}px ${textStyle.fontFamily}`;
    }
    const colors: ColorPalette = options.colors;
    const themeStyles = scene.geometry.getThemeStyles();
    const legendColor = resolveThemeColor(themeStyles, colors, ['legendTextColor', 'text', 'textSecondary', 'axisGuideColor', 'statusYellow']);
    const realtimeColor = resolveThemeColor(themeStyles, colors, ['statusRed', 'statusYellow', 'axisGuideColor', 'text', 'primary']);
    type LegendRun = { text: string; color: string; alpha: number; width: number };
    let currentRow: LegendRun[] = [];
    const rows: LegendRun[][] = [currentRow];
    let rowWidth = 0;
    if (status) {
        const key = `status${String(status)[0]?.toUpperCase()}${String(status).slice(1)}`;
        const statusColor = colors[key];
        if (statusColor) {
            const width = context.measureText(statusMarkerSpacing).width;
            currentRow.push({ text: statusMarker, color: statusColor, alpha: 1, width });
            rowWidth += width;
        }
    }
    const lineHeight = 18;
    const maxRows = narrow ? 1 : max(1, Math.floor((scene.state.padding.top - 4) / lineHeight));
    const separatorWidth = context.measureText(partSeparator).width;
    for (let index = 0; index < parts.length; index += 1) {
        const part = `${index === 0 ? metricNamePrefix : ''}${parts[index] ?? ''}`;
        const partWidth = context.measureText(part).width;
        if (index > 0 && rowWidth + separatorWidth + partWidth > legendMaxWidth && rows.length < maxRows) {
            currentRow = [];
            rows.push(currentRow);
            rowWidth = 0;
        } else if (index > 0) {
            currentRow.push({ text: partSeparator, color: legendColor, alpha: 0.42, width: separatorWidth });
            rowWidth += separatorWidth;
        }
        const realtimeIndex = realtimeLabel ? part.indexOf(realtimeLabel) : -1;
        if (realtimeIndex === -1) {
            currentRow.push({ text: part, color: legendColor, alpha: 1, width: partWidth });
        } else {
            const before = part.slice(0, realtimeIndex);
            const after = part.slice(realtimeIndex + realtimeLabel.length);
            currentRow.push({ text: before, color: legendColor, alpha: 1, width: context.measureText(before).width }, { text: realtimeLabel, color: realtimeColor, alpha: 1, width: context.measureText(realtimeLabel).width }, { text: after, color: legendColor, alpha: 1, width: context.measureText(after).width });
        }
        rowWidth += partWidth;
    }
    const baseAlpha = context.globalAlpha;
    const firstY = scene.state.padding.top - 16 - lineHeight * (rows.length - 1);
    for (const [rowIndex, row] of rows.entries()) {
        const width = row.reduce((total, run) => total + run.width, 0);
        const scale = min(1, legendMaxWidth / max(1, width));
        context.save();
        context.transform(scale, 0, 0, 1, anchorX * (1 - scale), 0);
        let cursor = 0;
        for (const run of row) {
            context.direction = hasRtlScriptLetters(run.text) ? 'rtl' : 'ltr';
            context.fillStyle = run.color;
            context.globalAlpha = baseAlpha * run.alpha;
            context.fillText(run.text, anchorX + directionSign * cursor, firstY + rowIndex * lineHeight);
            cursor += run.width;
        }
        context.restore();
    }
    context.restore();
};

export { drawCrosshair, drawTooltip, drawLegend };
