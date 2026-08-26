/* SoAI - Charts feature runtime [frontend/assets/ts/features/charts/Runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isFunction } from '@core/typeGuards.ts';

interface LayerEntry {
    name: LayerName;
    canvas: HTMLCanvasElement;
    context: CanvasRenderingContext2D;
}

interface AcquireOptions {
    zBase?: number;
}

type LayerName = 'static' | 'data' | 'interaction';

const DEFAULT_LAYER_ORDER: readonly LayerName[] = Object.freeze(['static', 'data', 'interaction']);

const detachCanvas = (canvas: HTMLCanvasElement | null): void => {
    if (!canvas) {
        return;
    }
    if (isFunction(canvas.remove)) {
        canvas.remove();
    } else if (canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
    }
};

const configureCanvas = (canvas: HTMLCanvasElement, name: LayerName): void => {
    canvas.className = `chart-layer chart-layer-${name}`;
};

const createLayer = (documentRef: Document, name: LayerName): LayerEntry => {
    const canvas = documentRef.createElement('canvas');
    configureCanvas(canvas, name);
    const contextOptions: CanvasRenderingContext2DSettings = { desynchronized: true, alpha: true };
    let context: CanvasRenderingContext2D | null = canvas.getContext('2d', contextOptions);
    if (!context) {
        context = canvas.getContext('2d');
    }
    if (!context) {
        throw new Error('Chart runtime failed to acquire 2D context');
    }
    return { name, canvas, context };
};

const resetContext = (entry: LayerEntry | null): void => {
    if (!entry?.context || !entry.canvas) {
        return;
    }
    const { context, canvas } = entry;
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, canvas.width, canvas.height);
    canvas.width = 0;
    canvas.height = 0;
};

class ChartLayerPool {
    #document: Document;
    #pools: Map<LayerName, LayerEntry[]> = new Map();

    constructor(document: Document) {
        if (!document) {
            throw new Error('ChartLayerPool requires a Document');
        }
        this.#document = document;
    }

    #ensurePool(name: LayerName): LayerEntry[] {
        if (!this.#pools.has(name)) {
            this.#pools.set(name, []);
        }
        const pool = this.#pools.get(name);
        if (!pool) {
            throw new Error(`ChartLayerPool failed to create pool for "${name}"`);
        }
        return pool;
    }

    #acquireLayer(name: LayerName): LayerEntry {
        const pool = this.#ensurePool(name);
        const pooled = pool.pop();
        const entry = pooled ?? createLayer(this.#document, name);
        detachCanvas(entry.canvas);
        return entry;
    }

    #releaseLayer(entry: LayerEntry | null): void {
        if (!entry || !entry.canvas) {
            return;
        }
        resetContext(entry);
        detachCanvas(entry.canvas);
        configureCanvas(entry.canvas, entry.name);
        dom.setStyle(entry.canvas, 'zIndex', null);
        this.#ensurePool(entry.name).push(entry);
    }

    acquireLayers(names: readonly LayerName[] = DEFAULT_LAYER_ORDER, options: AcquireOptions = {}): LayerEntry[] {
        const resolved: LayerEntry[] = [];
        const base = Number.isFinite(options.zBase) ? Number(options.zBase) : 0;
        names.forEach((name, index) => {
            const entry = this.#acquireLayer(name);
            dom.setStyle(entry.canvas, 'zIndex', String(base + index));
            resolved.push(entry);
        });
        return resolved;
    }

    releaseLayers(entries: readonly LayerEntry[] | null): void {
        if (!entries) return;
        entries.forEach((entry) => this.#releaseLayer(entry));
    }
}

const createChartLayerPool = (document: Document): ChartLayerPool => new ChartLayerPool(document);

export { ChartLayerPool, createChartLayerPool };
export type { LayerEntry, AcquireOptions, LayerName };
