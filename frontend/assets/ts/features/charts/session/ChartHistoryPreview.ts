/* SoAI - Chart older-history preview timeline ownership [frontend/assets/ts/features/charts/session/ChartHistoryPreview.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { ChartHistoryStatus } from '@features/charts/chartTypes.ts';
import type { RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import type { ChartConfigurationState, ChartViewportState } from '@features/charts/session/chartState.ts';
import { easeOutCubic } from '@features/charts/viewport/easing.ts';

interface HistoryRevealSpan {
    fromTs: number;
    toTs: number;
    alpha: number;
}

interface HistoryPreviewFrame {
    status: ChartHistoryStatus;
    loading: boolean;
    ghostAnchorTs: number;
    ghostAlpha: number;
    shimmerAlpha: number;
    shimmerPhase: number;
    reveals: readonly HistoryRevealSpan[];
    boundaryAlpha: number;
    spinnerTurn: number;
}

interface ChartHistoryPreviewDependencies {
    element: HTMLElement;
    configuration: ChartConfigurationState;
    viewportState: Pick<ChartViewportState, 'historyBoundaryHitAt'>;
    series: { readonly dataLength: number; readonly timestamps: Float64Array };
    viewport: { getRenderGeometry(): RenderGeometry | null };
}

const GHOST_FADE_IN_MS = 150;
const SHIMMER_MS = 400;
const CROSSFADE_MS = 320;
const BOUNDARY_MS = 700;
const SPINNER_PERIOD_MS = 900;

const fadeIn = (elapsedMs: number, durationMs: number): number => (durationMs <= 0 || !Number.isFinite(elapsedMs) ? 1 : clampNumber(elapsedMs / durationMs, 0, 1));

const fadeOut = (elapsedMs: number, durationMs: number): number => (durationMs <= 0 || !(elapsedMs >= 0) || elapsedMs >= durationMs ? 0 : 1 - elapsedMs / durationMs);

const easeOutRemaining = (elapsedMs: number, durationMs: number): number => 1 - easeOutCubic(1 - fadeOut(elapsedMs, durationMs));

const envelope = (elapsedMs: number, durationMs: number): number => {
    const edgeMs = durationMs * 0.3;
    if (durationMs <= 0 || !(elapsedMs >= 0) || elapsedMs >= durationMs) return 0;
    return Math.min(1, elapsedMs / edgeMs, (durationMs - elapsedMs) / edgeMs);
};

class ChartHistoryPreview {
    readonly #dependencies: ChartHistoryPreviewDependencies;
    #status: ChartHistoryStatus = 'idle';
    #loadingSince = Number.NaN;
    #settledAt = Number.NaN;
    #oldestSeenTs = Number.NaN;
    #reveals: Array<{ fromTs: number; toTs: number; at: number }> = [];

    constructor(dependencies: ChartHistoryPreviewDependencies) {
        this.#dependencies = dependencies;
    }

    frame(now: number): HistoryPreviewFrame {
        const crossfadeMs = this.#duration(CROSSFADE_MS);
        this.#observe(now, crossfadeMs);
        const loading = this.#status === 'loading';
        return {
            status: this.#status,
            loading,
            ghostAnchorTs: this.#oldestSeenTs,
            ghostAlpha: loading ? fadeIn(now - this.#loadingSince, this.#duration(GHOST_FADE_IN_MS)) : easeOutRemaining(now - this.#settledAt, crossfadeMs),
            shimmerAlpha: loading ? envelope(now - this.#loadingSince, this.#duration(SHIMMER_MS)) : 0,
            shimmerPhase: Number.isFinite(this.#loadingSince) ? (now - this.#loadingSince) / SHIMMER_MS : 0,
            reveals: this.#reveals.map(({ fromTs, toTs, at }) => ({ fromTs, toTs, alpha: easeOutRemaining(now - at, crossfadeMs) })).filter((reveal) => reveal.alpha > 0),
            boundaryAlpha: fadeOut(now - this.#dependencies.viewportState.historyBoundaryHitAt, this.#duration(BOUNDARY_MS)),
            spinnerTurn: (now % SPINNER_PERIOD_MS) / SPINNER_PERIOD_MS
        };
    }

    isAnimating(now: number): boolean {
        const frame = this.frame(now);
        if (frame.reveals.length > 0 || frame.boundaryAlpha > 0 || (!frame.loading && frame.ghostAlpha > 0)) return true;
        if (!frame.loading) return false;
        const geometry = this.#dependencies.viewport.getRenderGeometry();
        return geometry !== null && Number.isFinite(frame.ghostAnchorTs) && geometry.startTs < frame.ghostAnchorTs;
    }

    #observe(now: number, crossfadeMs: number): void {
        const { series, configuration } = this.#dependencies;
        const oldestTs = series.dataLength > 0 ? (series.timestamps[0] ?? Number.NaN) : Number.NaN;
        const status = configuration.options.history?.status ?? 'idle';
        const wasLoading = this.#status === 'loading';
        if (!(oldestTs <= this.#oldestSeenTs)) this.#reveals = [];
        else this.#reveals = this.#reveals.filter((reveal) => now - reveal.at < crossfadeMs);
        if ((wasLoading || status === 'loading') && oldestTs < this.#oldestSeenTs) this.#reveals.push({ fromTs: oldestTs, toTs: this.#oldestSeenTs, at: now });
        if (status !== this.#status) {
            if (status === 'loading') this.#loadingSince = now;
            else if (wasLoading) this.#settledAt = now;
            this.#status = status;
        }
        this.#oldestSeenTs = oldestTs;
    }

    #duration(baseMs: number): number {
        return scaleAnimationDurationMs(baseMs, this.#dependencies.element);
    }
}

export { ChartHistoryPreview };
export type { ChartHistoryPreviewDependencies, HistoryPreviewFrame, HistoryRevealSpan };
