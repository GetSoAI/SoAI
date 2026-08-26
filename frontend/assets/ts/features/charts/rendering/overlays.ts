/* SoAI - Charts feature overlays [frontend/assets/ts/features/charts/rendering/overlays.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import type { ChartOptions, ColorPalette, CrosshairState } from '@features/charts/chartTypes.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { drawCoordinateLabel, drawRoundedRect, requireThemeColor, resolveThemeColor } from '@features/charts/rendering/primitives.ts';

const { max, min, round } = Math;

const optionalFiniteNumber = (value: JsonValue | null | undefined): number | null => (isFiniteNumber(value) ? value : null);

const formatNumberDelta = (prefix: string, value: number, formatValue: (value: number) => string): string => `${prefix}${value >= 0 ? '+' : ''}${formatValue(value)}`;

const getOhlcMetadata = (): { open: string; high: string; low: string; close: string } => ({
    open: i18n.t('charts.legend.openPrefix'),
    high: i18n.t('charts.legend.highPrefix'),
    low: i18n.t('charts.legend.lowPrefix'),
    close: i18n.t('charts.legend.closePrefix')
});

const isOhlcType = (scene: ChartRenderingScene, options: ChartOptions): boolean => scene.buffers.isOhlcRenderingType(options.chartType) ?? isOhlcChartType(options.chartType);

const drawTooltip = (scene: ChartRenderingScene, context: CanvasRenderingContext2D): void => {
    const crosshair: CrosshairState = scene.state.crosshair;
    const { x: xCoordinate, y: yCoordinate, value, timestamp, open, high, low, close, datasetValues } = crosshair;
    const theme = scene.geometry.getThemeStyles();
    const options: ChartOptions = scene.state.chartOptions;
    const colors: ColorPalette = options.colors;
    const isCandle = isOhlcType(scene, options);

    const lines: { text: string; font?: string | undefined; color?: string | undefined }[] = [];
    if (isCandle) {
        const meta = getOhlcMetadata();
        if (isFiniteNumber(open)) lines.push({ text: `${meta.open}${scene.format.formatValue(open)}` });
        if (isFiniteNumber(high)) lines.push({ text: `${meta.high}${scene.format.formatValue(high)}` });
        if (isFiniteNumber(low)) lines.push({ text: `${meta.low}${scene.format.formatValue(low)}` });
        const closeValue = isFiniteNumber(close) ? close : isFiniteNumber(value) ? value : null;
        if (closeValue !== null) lines.push({ text: `${meta.close}${scene.format.formatValue(closeValue)}` });
    } else if (isFiniteNumber(value)) {
        lines.push({ text: scene.format.formatValue(value) });
    }

    if (isFiniteNumber(timestamp)) {
        lines.push({
            text: String(scene.format.formatDetailedTimestamp(timestamp, { includeSeconds: true, includeMilliseconds: (scene.geometry.getVisibleTimeSpan?.() ?? 0) <= 5000 })),
            font: '11px sans-serif',
            color: resolveThemeColor(theme, colors, ['textSecondary', 'text', 'axisGuideColor']) || undefined
        });
    }

    if (datasetValues) {
        const nameValueSeparator = i18n.t('charts.legend.nameValueSeparator');
        const dsCols = [colors['secondary'], colors['tertiary'], colors['quaternary'], colors['statusGreen'], colors['statusYellow'], colors['statusRed'], colors['textSecondary']].filter((item): item is string => Boolean(item));
        const defaultColor = resolveThemeColor(theme, colors, ['legendTextColor', 'text', 'textSecondary', 'statusGreen']) || undefined;
        let colorIndex = 0;
        for (const [name, rawValue] of Object.entries(datasetValues)) {
            lines.push({
                text: `${name}${nameValueSeparator}${scene.format.formatValue(rawValue)}`,
                font: '11px sans-serif',
                color: dsCols.length > 0 ? dsCols[colorIndex % dsCols.length] : defaultColor
            });
            colorIndex += 1;
        }
    }

    const tooltipBg = resolveThemeColor(theme, colors, ['tooltipBackground', 'background', 'textSecondary', 'text', 'crosshair', 'axisGuideColor']);
    const tooltipText = resolveThemeColor(theme, colors, ['tooltipTextColor', 'text', 'legendTextColor', 'textSecondary', 'statusRed']);

    context.save();
    context.font = '12px sans-serif';
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
        context.font = line.font ?? '12px sans-serif';
        context.fillStyle = line.color ?? tooltipText;
        context.textAlign = 'left';
        context.textBaseline = 'middle';
        context.fillText(line.text, boxX + boxPaddingX, boxY + boxPaddingY + lineHeight * (index + 0.5));
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

    if (scene.state.chartOptions.showAxisCoordinates && isFiniteNumber(value)) {
        drawCoordinateLabel(context, dims.right + 4 + (context.measureText(scene.format.formatValue(value)).width + 16) / 2, yCoordinate, scene.format.formatValue(value), {
            bgColor: requireThemeColor(themeStyles, 'crosshairValueBackground'),
            textColor: requireThemeColor(themeStyles, 'crosshairValueTextColor')
        });
        drawTooltip(scene, context);
    }
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
    if (crosshair.visible && isFiniteNumber(crosshair.timestamp)) {
        parts.push(String(scene.format.formatDetailedTimestamp(crosshair.timestamp, { includeSeconds: span <= 90000 })));
    }

    const options: ChartOptions = scene.state.chartOptions;
    if (isOhlcType(scene, options)) {
        const openNumber = optionalFiniteNumber(open);
        const highNumber = optionalFiniteNumber(high);
        const lowNumber = optionalFiniteNumber(low);
        const closeValue = closeNumber ?? valueNumber;
        if (openNumber !== null) parts.push(`${meta.open}${scene.format.formatValue(openNumber)}`);
        if (highNumber !== null) parts.push(`${meta.high}${scene.format.formatValue(highNumber)}`);
        if (lowNumber !== null) parts.push(`${meta.low}${scene.format.formatValue(lowNumber)}`);
        if (closeValue !== null) parts.push(`${meta.close}${scene.format.formatValue(closeValue)}`);
    } else if (valueNumber !== null) {
        parts.push(scene.format.formatValue(valueNumber));
    }

    const deltaNumber = optionalFiniteNumber(delta);
    if (options.showDelta && deltaNumber !== null) parts.push(formatNumberDelta(deltaPrefix, deltaNumber, (value) => scene.format.formatValue(value)));
    const minNumber = optionalFiniteNumber(mn);
    const maxNumber = optionalFiniteNumber(mx);
    if (minNumber !== null) parts.push(`${minPrefix}${scene.format.formatValue(minNumber)}`);
    if (maxNumber !== null) parts.push(`${maxPrefix}${scene.format.formatValue(maxNumber)}`);

    const baselineNumber = optionalFiniteNumber(baseline);
    if (options.chartType === 'deviation' && baselineNumber !== null) {
        parts.push(`${baselinePrefix}${scene.format.formatValue(baselineNumber)}`);
        if (valueNumber !== null) parts.push(formatNumberDelta(deviationPrefix, valueNumber - baselineNumber, (value) => scene.format.formatValue(value)));
    } else {
        const avgNumber = optionalFiniteNumber(avg);
        if (avgNumber !== null) parts.push(`${avgPrefix}${scene.format.formatValue(avgNumber)}`);
    }

    const datasetValues = crosshair.datasetValues;
    if (datasetValues) {
        for (const [name, rawValue] of Object.entries(datasetValues)) parts.push(`${name}${nameValueSeparator}${scene.format.formatValue(rawValue)}`);
    }

    const timestampNumber = optionalFiniteNumber(timestamp);
    if (options.showLegendTimestamp && timestampNumber !== null) {
        const age = serverEpochMs() - timestampNumber;
        parts.push(age < 5000 ? realtimeLabel : age < 60000 ? `${round(age / 1000)}${secondsAgoSuffix}` : String(scene.format.formatTimestamp(timestampNumber, 'full')));
    }

    const metricNamePrefix = options.metricName ? `${options.metricName}${metricNameSeparator}` : '';
    const legendText = `${metricNamePrefix}${parts.join(partSeparator)}`;
    context.font = '11px monospace';
    const chartDims = scene.geometry.getChartDimensions();
    const lx = scene.state.padding.left;
    const ly = scene.state.padding.top - 16;
    Object.assign(context, { textAlign: 'left', textBaseline: 'top' });

    let tx = lx;
    const colors: ColorPalette = options.colors;
    if (status) {
        const key = `status${String(status)[0]?.toUpperCase()}${String(status).slice(1)}`;
        const statusColor = colors[key];
        if (statusColor) {
            context.fillStyle = statusColor;
            context.fillText(statusMarker, tx, ly);
            tx += context.measureText(statusMarkerSpacing).width;
        }
    }

    const themeStyles = scene.geometry.getThemeStyles();
    const legendColor = resolveThemeColor(themeStyles, colors, ['legendTextColor', 'text', 'textSecondary', 'axisGuideColor', 'statusYellow']);
    const realtimeIndex = realtimeLabel ? legendText.indexOf(realtimeLabel) : -1;
    const legendMaxWidth = max(1, chartDims.right - tx);

    if (realtimeIndex !== -1) {
        const pre = legendText.slice(0, realtimeIndex);
        const post = legendText.slice(realtimeIndex + realtimeLabel.length);
        if (context.measureText(legendText).width > legendMaxWidth) {
            context.fillStyle = legendColor;
            context.fillText(legendText, tx, ly, legendMaxWidth);
            return;
        }
        context.fillStyle = legendColor;
        context.fillText(pre, tx, ly);
        const w1 = context.measureText(pre).width;
        context.fillStyle = resolveThemeColor(themeStyles, colors, ['statusRed', 'statusYellow', 'axisGuideColor', 'text', 'primary']);
        context.fillText(realtimeLabel, tx + w1, ly);
        context.fillStyle = legendColor;
        context.fillText(post, tx + w1 + context.measureText(realtimeLabel).width, ly);
    } else {
        context.fillStyle = legendColor;
        context.fillText(legendText, tx, ly, legendMaxWidth);
    }
};

export { drawCrosshair, drawTooltip, drawLegend };
