/* SoAI - Chart redraw state and notification ownership [frontend/assets/ts/features/charts/session/ChartRedrawQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { VisiblePointsCache } from '@features/charts/chartTypes.ts';
import type { RedrawRequest } from '@features/charts/component/chartComponentTypes.ts';
import type { AxisCache } from '@features/charts/rendering/renderingModels.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type ChartRenderLayer = 'static' | 'data' | 'interaction';
type RedrawListener = () => void;
const CHART_RENDER_LAYERS: readonly ChartRenderLayer[] = ['static', 'data', 'interaction'];

class ChartRedrawQueue {
    readonly #listeners = new Set<RedrawListener>();
    readonly #pending: Record<ChartRenderLayer, boolean> = { static: true, data: true, interaction: true };
    #visiblePoints: VisiblePointsCache | null = null;
    #axis: AxisCache | null = null;
    #legend: Record<string, JsonValue | null | undefined> = {};

    get hasPending(): boolean {
        return this.#pending.static || this.#pending.data || this.#pending.interaction;
    }

    isPending(layer: ChartRenderLayer): boolean {
        return this.#pending[layer];
    }

    request(requirements: RedrawRequest = { data: true, interaction: true }): void {
        if (requirements.data || requirements.static) {
            this.#visiblePoints = null;
            this.#axis = null;
        }
        for (const layer of CHART_RENDER_LAYERS) {
            if (requirements[layer]) this.#pending[layer] = true;
        }
        for (const listener of [...this.#listeners]) listener();
    }

    complete(layer: ChartRenderLayer): void {
        this.#pending[layer] = false;
    }

    subscribe(listener: RedrawListener): () => void {
        this.#listeners.add(listener);
        return () => this.#listeners.delete(listener);
    }

    get visiblePoints(): VisiblePointsCache | null {
        return this.#visiblePoints;
    }

    set visiblePoints(value: VisiblePointsCache | null) {
        this.#visiblePoints = value;
    }

    get axis(): AxisCache | null {
        return this.#axis;
    }

    set axis(value: AxisCache | null) {
        this.#axis = value;
    }

    get legend(): Record<string, JsonValue | null | undefined> {
        return this.#legend;
    }

    set legend(value: Record<string, JsonValue | null | undefined>) {
        this.#legend = value;
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
    }

    destroy(): void {
        this.#listeners.clear();
        this.#visiblePoints = null;
        this.#axis = null;
        this.#legend = {};
        this.#pending.static = false;
        this.#pending.data = false;
        this.#pending.interaction = false;
    }
}

export { ChartRedrawQueue };
export type { ChartRenderLayer, RedrawListener };
