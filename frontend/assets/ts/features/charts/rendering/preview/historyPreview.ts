/* SoAI - Charts feature older-history preview rendering [frontend/assets/ts/features/charts/rendering/preview/historyPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import { findFirstIndexAtOrAfter } from '@features/charts/component/data/timestampIndex.ts';
import { getValueViewport } from '@features/charts/rendering/axes.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { clipToPlotArea, resolvePlotBackground } from '@features/charts/rendering/frame.ts';
import { buildHistoryGhost, type HistoryGhostPoint } from '@features/charts/rendering/preview/historyGhost.ts';
import { drawCoordinateLabel } from '@features/charts/rendering/primitives.ts';
import type { ChartDimensions, RenderGeometry, ValueViewport } from '@features/charts/rendering/renderingModels.ts';
import { resolveCandlestickPalette, resolvePrimarySeriesColor } from '@features/charts/rendering/series/service.ts';
import { createAreaFill } from '@features/charts/rendering/series/view.ts';
import type { HistoryPreviewFrame, HistoryRevealSpan } from '@features/charts/session/ChartHistoryPreview.ts';
import { timeToX } from '@features/charts/viewport/timeViewport.ts';

const GHOST_ALPHA = 0.32;
const REVEAL_ERASE_FILL = '#000';
const GHOST_MIN_STEP_PX = 2;
const HATCH_SPACING_PX = 10;
const SPINNER_RADIUS_PX = 6;
const RETRY_GLYPH = '\u21bb';
const LABEL_FONT = '600 12px sans-serif';
const LABEL_PADDING_PX = 16;

interface PreviewSpan {
    left: number;
    right: number;
    top: number;
    bottom: number;
}

const resolveMutedColor = (scene: ChartRenderingScene): string => {
    const colors = scene.state.chartOptions.colors;
    return scene.geometry.getThemeStyles()?.legendTextColor || colors.textSecondary || colors.text || colors.grid || '';
};

const traceGhostLine = (context: CanvasRenderingContext2D, ghost: readonly HistoryGhostPoint[], geometry: RenderGeometry, toY: (value: number) => number): void => {
    context.beginPath();
    ghost.forEach((point, index) => {
        const pointX = timeToX(geometry, point.timestamp);
        if (index === 0) context.moveTo(pointX, toY(point.close));
        else context.lineTo(pointX, toY(point.close));
    });
};

const drawGhostSeries = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, geometry: RenderGeometry, viewport: ValueViewport, ghost: readonly HistoryGhostPoint[], ohlc: boolean): void => {
    const toY = (value: number): number => scene.format.valueToPixel(value, viewport.height, viewport.top);
    const spacing = ghost.length > 1 && ghost[0] && ghost[1] ? Math.abs(ghost[0].timestamp - ghost[1].timestamp) / geometry.msPerPx : geometry.slotWidth;
    const chartType = scene.state.chartOptions.chartType;
    if (ohlc) {
        const palette = resolveCandlestickPalette(scene);
        const bodyWidth = Math.max(1.4, Math.min(32, spacing * 0.7));
        for (const point of ghost) {
            const pointX = timeToX(geometry, point.timestamp);
            const color = point.close >= point.open ? palette.up : palette.down;
            const openY = toY(point.open);
            const closeY = toY(point.close);
            context.strokeStyle = color;
            context.fillStyle = color;
            context.lineWidth = 1;
            context.beginPath();
            context.moveTo(pointX, toY(point.high));
            context.lineTo(pointX, toY(point.low));
            context.stroke();
            context.fillRect(pointX - bodyWidth / 2, Math.min(openY, closeY), bodyWidth, Math.max(1, Math.abs(closeY - openY)));
        }
        return;
    }
    const color = resolvePrimarySeriesColor(scene);
    if (chartType === 'bar') {
        const barWidth = Math.max(1, Math.min(22, spacing * 0.65));
        context.fillStyle = color;
        for (const point of ghost) {
            const valueY = toY(point.close);
            context.fillRect(timeToX(geometry, point.timestamp) - barWidth / 2, Math.min(valueY, viewport.bottom), barWidth, Math.max(1, Math.abs(viewport.bottom - valueY)));
        }
        return;
    }
    if (chartType === 'area') {
        const last = ghost[ghost.length - 1];
        const first = ghost[0];
        if (first && last) {
            traceGhostLine(context, ghost, geometry, toY);
            context.lineTo(timeToX(geometry, last.timestamp), viewport.bottom);
            context.lineTo(timeToX(geometry, first.timestamp), viewport.bottom);
            context.closePath();
            context.fillStyle = createAreaFill(context, viewport, color);
            context.fill();
        }
    }
    context.strokeStyle = color;
    context.lineWidth = 2;
    traceGhostLine(context, ghost, geometry, toY);
    context.stroke();
};

const drawGhost = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry, frame: HistoryPreviewFrame): void => {
    const { timestamps, dataLength } = scene.state;
    const anchorIndex = findFirstIndexAtOrAfter(timestamps, dataLength, frame.ghostAnchorTs);
    if (anchorIndex === -1 || timestamps[anchorIndex] !== frame.ghostAnchorTs || frame.ghostAnchorTs <= geometry.startTs) return;
    const ohlcBuffers = isOhlcChartType(scene.state.chartOptions.chartType) ? scene.buffers.getRenderableOhlcBuffers() : null;
    const ghost = buildHistoryGhost({
        timestamps,
        dataLength,
        anchorIndex,
        values: scene.buffers.getValueBufferForRendering?.() ?? scene.state.values,
        ohlc: ohlcBuffers,
        intervalMs: geometry.slotWidth * geometry.msPerPx,
        minStepMs: geometry.msPerPx * GHOST_MIN_STEP_PX,
        untilTs: geometry.startTs
    });
    context.save();
    context.beginPath();
    context.rect(dims.left, dims.top, Math.max(0, timeToX(geometry, frame.ghostAnchorTs) - dims.left), dims.chartHeight);
    context.clip();
    context.globalAlpha = GHOST_ALPHA * frame.ghostAlpha;
    drawGhostSeries(scene, context, geometry, getValueViewport(scene, dims), ghost, ohlcBuffers !== null);
    context.restore();
};

const drawShimmer = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, span: PreviewSpan, frame: HistoryPreviewFrame): void => {
    const height = span.bottom - span.top;
    const offset = (frame.shimmerPhase * HATCH_SPACING_PX * 2) % HATCH_SPACING_PX;
    context.save();
    context.beginPath();
    context.rect(span.left, span.top, span.right - span.left, height);
    context.clip();
    context.globalAlpha = 0.22 * frame.shimmerAlpha;
    context.strokeStyle = resolveMutedColor(scene);
    context.lineWidth = 1;
    context.beginPath();
    for (let hatchX = span.left - height + offset; hatchX < span.right; hatchX += HATCH_SPACING_PX) {
        context.moveTo(hatchX, span.bottom);
        context.lineTo(hatchX + height, span.top);
    }
    context.stroke();
    context.restore();
};

const drawSpanLabel = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, span: PreviewSpan, text: string, compactText: string, spinnerTurn: number | null): void => {
    const width = span.right - span.left;
    const centerX = (span.left + span.right) / 2;
    const centerY = (span.top + span.bottom) / 2;
    const color = resolveMutedColor(scene);
    context.save();
    context.font = LABEL_FONT;
    const spinnerSpace = spinnerTurn === null ? 0 : SPINNER_RADIUS_PX * 2 + 8;
    const fullWidth = context.measureText(text).width + LABEL_PADDING_PX;
    const label = width >= fullWidth + spinnerSpace + 16 ? text : compactText;
    const labelWidth = label === text ? fullWidth : context.measureText(label).width + LABEL_PADDING_PX;
    const showLabel = label !== '' && width >= labelWidth + spinnerSpace + 16;
    if (showLabel) drawCoordinateLabel(context, clampNumber(centerX - spinnerSpace / 2, span.left + labelWidth / 2 + 8, span.right - labelWidth / 2 - spinnerSpace - 8), centerY, label, { bgColor: resolvePlotBackground(scene), textColor: color, font: LABEL_FONT });
    if (spinnerTurn !== null && width >= spinnerSpace + 8) {
        const spinnerX = showLabel ? Math.min(span.right - SPINNER_RADIUS_PX - 8, centerX + labelWidth / 2) : centerX;
        const start = spinnerTurn * Math.PI * 2;
        context.strokeStyle = color;
        context.lineWidth = 2;
        context.lineCap = 'round';
        context.beginPath();
        context.arc(spinnerX, centerY, SPINNER_RADIUS_PX, start, start + Math.PI * 1.5);
        context.stroke();
    }
    context.restore();
};

const drawReveal = (context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry, reveal: HistoryRevealSpan): void => {
    const left = Math.max(dims.left, timeToX(geometry, reveal.fromTs));
    const right = Math.min(dims.right, timeToX(geometry, reveal.toTs));
    if (!(right > left)) return;
    context.save();
    context.globalCompositeOperation = 'destination-out';
    context.globalAlpha = (1 - GHOST_ALPHA) * reveal.alpha;
    context.fillStyle = REVEAL_ERASE_FILL;
    context.fillRect(left, dims.top, right - left, dims.chartHeight);
    context.restore();
};

const drawBoundary = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, boundaryX: number, alpha: number): void => {
    context.save();
    context.globalAlpha = 0.7 * alpha;
    context.strokeStyle = resolveMutedColor(scene);
    context.lineWidth = 1;
    context.setLineDash([4, 4]);
    context.beginPath();
    context.moveTo(boundaryX, dims.top);
    context.lineTo(boundaryX, dims.top + dims.chartHeight);
    context.stroke();
    context.restore();
};

const drawHistoryPreview = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, dims: ChartDimensions, geometry: RenderGeometry, frame: HistoryPreviewFrame): void => {
    const oldestTs = scene.state.timestamps[0];
    if (scene.state.dataLength === 0 || oldestTs === undefined || dims.chartWidth <= 0) return;
    const leadingX = clampNumber(timeToX(geometry, oldestTs), dims.left, dims.right);
    const span: PreviewSpan = { left: dims.left, right: leadingX, top: dims.top, bottom: dims.top + dims.chartHeight };
    context.save();
    clipToPlotArea(scene, context, dims);
    for (const reveal of frame.reveals) drawReveal(context, dims, geometry, reveal);
    if (frame.ghostAlpha > 0) drawGhost(scene, context, dims, geometry, frame);
    if (leadingX > dims.left) {
        if (frame.shimmerAlpha > 0) drawShimmer(scene, context, span, frame);
        if (frame.loading) drawSpanLabel(scene, context, span, i18n.t('charts.loadingState'), '', frame.spinnerTurn);
        else if (frame.status === 'failed') drawSpanLabel(scene, context, span, `${RETRY_GLYPH} ${i18n.t('charts.historyFailed')}`, RETRY_GLYPH, null);
    }
    if (frame.boundaryAlpha > 0) drawBoundary(scene, context, dims, leadingX, frame.boundaryAlpha);
    context.restore();
};

export { drawHistoryPreview };
