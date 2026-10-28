/* SoAI - Hardware widget chart geometry motion [frontend/assets/ts/features/hardware/widgets/basehardwarewidget/chartMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { easeOutCubic, scaleChartAnimationDurationMs, SERIES_TRANSITION_MS } from '@core/animations/chartMotion.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { scheduleRequiredRender } from '@core/runtime/animationFrames.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { WIDGET_CONSTANTS } from '@features/hardware/widgets/constants.ts';
import type { DataPoint, MetricChartNormalizer, WidgetElements } from '@features/hardware/widgets/contracts.ts';
import { createSmoothPathValues, type ChartPoint } from '@features/hardware/widgets/mappers.ts';
import { buildWidgetChartSeries, resolveWidgetWindowDurationMs } from '@features/hardware/widgets/basehardwarewidget/effects.ts';

class HardwareWidgetChartMotion {
    #area: SVGPathElement | null = null;
    #line: SVGPathElement | null = null;
    #visible: ChartPoint[] = [];
    #from: ChartPoint[] = [];
    #target: ChartPoint[] = [];
    #metric = '';
    #visibleNow = 0;
    #fromNow = 0;
    #targetNow = 0;
    #startedAt = 0;
    #duration = 0;
    #cancelFrame: (() => void) | null = null;
    #disposed = false;

    constructor(resources: ResourceTracker) {
        resources.track(this.destroy);
    }

    update(elements: WidgetElements, points: readonly DataPoint[], metric: string, now: number, normalize: MetricChartNormalizer, dim: boolean): void {
        if (this.#disposed) return;
        this.stop();
        const area = elements.chartPath;
        const line = elements.chartLine;
        if (!area || !line) {
            this.#visible = [];
            return;
        }
        if (area !== this.#area || line !== this.#line) this.#visible = [];
        this.#area = area;
        this.#line = line;
        area.classList.toggle('hardware-observation-stale', dim);
        line.classList.toggle('hardware-observation-stale', dim);
        const target = buildWidgetChartSeries(points, metric, now, normalize);
        this.#duration = scaleChartAnimationDurationMs(SERIES_TRANSITION_MS, area);
        this.#target = target;
        this.#targetNow = now;
        if (metric !== this.#metric || this.#visible.length === 0 || target.length === 0 || this.#duration === 0) {
            this.#metric = metric;
            this.#visible = target;
            this.#visibleNow = now;
            this.#paint();
            return;
        }
        this.#from = this.#alignSource(target, now);
        this.#fromNow = this.#visibleNow;
        this.#startedAt = monotonicMs();
        this.#cancelFrame = scheduleRequiredRender(this.#advance);
    }

    stop(): void {
        this.#cancelFrame?.();
        this.#cancelFrame = null;
    }

    readonly destroy = (): void => {
        this.stop();
        this.#disposed = true;
        this.#area = null;
        this.#line = null;
        this.#visible = [];
        this.#from = [];
        this.#target = [];
    };

    #alignSource(target: readonly ChartPoint[], now: number): ChartPoint[] {
        const first = this.#visible[0];
        const last = this.#visible[this.#visible.length - 1];
        if (!first || !last) throw new Error('Widget chart motion requires visible source geometry');
        const shift = ((now - this.#visibleNow) / resolveWidgetWindowDurationMs()) * WIDGET_CONSTANTS.SVG_VIEWBOX;
        let cursor = 0;
        return target.map((point, index) => {
            const sourceX = index === 0 ? 0 : Math.max(first.x, Math.min(last.x, point.x + shift));
            while (cursor + 1 < this.#visible.length && (this.#visible[cursor + 1]?.x ?? Infinity) <= sourceX) cursor++;
            const left = this.#visible[cursor];
            if (!left) throw new Error('Widget chart motion source point is missing');
            const right = this.#visible[cursor + 1];
            const sourceY = right && right.x > left.x ? left.y + ((right.y - left.y) * (sourceX - left.x)) / (right.x - left.x) : left.y;
            return { x: sourceX, y: sourceY };
        });
    }

    #advance = (): void => {
        this.#cancelFrame = null;
        if (this.#disposed || !this.#area) return;
        const timestamp = monotonicMs();
        const elapsed = Math.max(0, timestamp - this.#startedAt);
        const finished = elapsed >= this.#duration || scaleChartAnimationDurationMs(SERIES_TRANSITION_MS, this.#area) === 0;
        const progress = finished ? 1 : easeOutCubic(elapsed / this.#duration);
        this.#visible = finished
            ? this.#target
            : this.#target.map((point, index) => {
                  const source = this.#from[index];
                  if (!source) throw new Error('Widget chart motion target has no source point');
                  return { x: source.x + (point.x - source.x) * progress, y: source.y + (point.y - source.y) * progress };
              });
        this.#visibleNow = this.#fromNow + (this.#targetNow - this.#fromNow) * progress;
        this.#paint();
        if (!finished) this.#cancelFrame = scheduleRequiredRender(this.#advance);
    };

    #paint(): void {
        const paths = createSmoothPathValues(this.#visible, WIDGET_CONSTANTS.SVG_VIEWBOX);
        this.#area?.setAttribute('d', paths.areaPath);
        this.#line?.setAttribute('d', paths.linePath);
    }
}

export { HardwareWidgetChartMotion };
