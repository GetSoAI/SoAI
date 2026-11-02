/* SoAI - Stable pane allocation measurement and capacity observation [frontend/assets/ts/core/pagepanes/geometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { parsePositiveCssPixelValue } from '@core/dom/attributes.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { measureLayoutBox, measureLayoutViewport, type GeometryDimensions } from '@core/layout/elementGeometry.ts';
import { ElementResizeRedrawWatcher } from '@core/layout/elementResizeRedraw.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { resolvePaneCapacity, type PaneCapacity, type PaneCapacityMeasurement } from '@core/pagepanes/capacity.ts';
import type { ResourceTracker } from '@core/resourcetracker/service.ts';
import { createDebouncedHandler, type ScheduledHandler } from '@core/timers/scheduledHandlers.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { runCleanupStepCollectingFailure, throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';

const measureAllocation = (root: HTMLElement): GeometryDimensions => {
    const box = measureLayoutBox(root);
    const styles = getComputedStyleStrict(root);
    return {
        width: box.width - parsePositiveCssPixelValue(styles.borderInlineStartWidth, 0) - parsePositiveCssPixelValue(styles.borderInlineEndWidth, 0) - parsePositiveCssPixelValue(styles.paddingInlineStart, 0) - parsePositiveCssPixelValue(styles.paddingInlineEnd, 0),
        height: box.height - parsePositiveCssPixelValue(styles.borderBlockStartWidth, 0) - parsePositiveCssPixelValue(styles.borderBlockEndWidth, 0) - parsePositiveCssPixelValue(styles.paddingBlockStart, 0) - parsePositiveCssPixelValue(styles.paddingBlockEnd, 0)
    };
};

const sameMeasurement = (left: PaneCapacityMeasurement, right: PaneCapacityMeasurement): boolean => left.contentWidth === right.contentWidth && left.gap === right.gap && left.paneBorderWidth === right.paneBorderWidth && left.viewport.width === right.viewport.width && left.viewport.height === right.viewport.height;

class PagePaneGeometry {
    readonly #resources: ResourceTracker;
    readonly #onChange: (capacity: PaneCapacity | null) => void;
    readonly #onFailure: (error: Error) => void;
    readonly #watcher = new ElementResizeRedrawWatcher({ measureDimensions: measureAllocation, tolerancePixels: 0 });
    readonly #expand: ScheduledHandler<[]>;
    readonly #listeners: (() => void)[] = [];
    #root: HTMLElement | null = null;
    #lastCapacity: PaneCapacity | null = null;
    #measurement: PaneCapacityMeasurement | null = null;
    #pendingExpansion: { measurement: PaneCapacityMeasurement; capacity: PaneCapacity } | null = null;
    #frame: number | null = null;
    #failure: Error | null = null;

    constructor(resources: ResourceTracker, onChange: (capacity: PaneCapacity | null) => void, onFailure: (error: Error) => void) {
        this.#resources = resources;
        this.#onChange = onChange;
        this.#onFailure = onFailure;
        this.#expand = createDebouncedHandler(this.#commitExpansion, 250, { setTimer: (callback, delay) => resources.setTimeout(callback, delay), clearTimer: (timer) => resources.clearTimeout(timer), nowMs: monotonicMs });
    }

    observe(root: HTMLElement): void {
        if (this.#root) throw new Error('Pane geometry already has an allocation root');
        this.#root = root;
        try {
            this.#watcher.observe(root, this.refresh);
            const windowRef = root.ownerDocument.defaultView;
            if (!windowRef) throw new Error('Pane geometry requires an owning window');
            this.#listeners.push(this.#resources.addEventListener(windowRef, 'resize', this.#scheduleMeasurement));
            this.#listeners.push(this.#resources.addEventListener(windowRef, INTERFACE_SCALE_CHANGED_EVENT, this.#scheduleMeasurement));
            this.refresh();
        } catch (error) {
            const failure = ensureError(error);
            const failures = [failure];
            runCleanupStepCollectingFailure(() => this.dispose(), failures);
            this.#fail(failures.length === 1 ? failure : new AggregateError(failures, 'Pane geometry observation failed'));
        }
    }

    getCapacity(): PaneCapacity | null {
        return this.#root?.isConnected && this.#measurement ? this.#lastCapacity : null;
    }

    reset(): void {
        this.#cancelPending();
        this.#measurement = null;
        this.#lastCapacity = null;
        this.#failure = null;
    }

    refresh = (): void => {
        if (!this.#root) return;
        this.#expand.cancel();
        this.#pendingExpansion = null;
        try {
            this.#applyMeasurement(this.#readMeasurement());
        } catch (error) {
            this.#fail(ensureError(error));
        }
    };

    dispose(): void {
        this.#root = null;
        this.reset();
        const failures: Error[] = [];
        runCleanupStepCollectingFailure(() => this.#watcher.disconnect(), failures);
        for (const release of [...this.#listeners]) {
            try {
                release();
                this.#listeners.splice(this.#listeners.indexOf(release), 1);
            } catch (error) {
                failures.push(ensureError(error));
            }
        }
        throwCollectedCleanupFailures(failures);
    }

    #readMeasurement(): PaneCapacityMeasurement | null {
        const root = this.#root;
        if (!root?.isConnected) return null;
        const dimensions = measureAllocation(root);
        if (!Number.isFinite(dimensions.width) || !Number.isFinite(dimensions.height) || dimensions.width <= 0 || dimensions.height <= 0) return null;
        const pane = dom.resolve(':scope > .page-pane', root);
        if (!pane) throw new Error('Pane geometry requires a mounted pane region');
        const styles = getComputedStyleStrict(root);
        const paneStyles = getComputedStyleStrict(pane);
        return { connected: true, contentWidth: dimensions.width, gap: parsePositiveCssPixelValue(styles.columnGap, 0), paneBorderWidth: parsePositiveCssPixelValue(paneStyles.borderInlineStartWidth, 0) + parsePositiveCssPixelValue(paneStyles.borderInlineEndWidth, 0), viewport: measureLayoutViewport(root) };
    }

    #applyMeasurement(measurement: PaneCapacityMeasurement | null): void {
        const previous = this.getCapacity();
        const capacity = measurement ? resolvePaneCapacity(measurement, this.#lastCapacity) : null;
        this.#measurement = capacity === null ? null : measurement;
        if (capacity === null) {
            if (previous !== null) this.#notify(null);
            return;
        }
        this.#failure = null;
        if (this.#lastCapacity === null || capacity <= this.#lastCapacity) {
            this.#lastCapacity = capacity;
            if (previous !== capacity) this.#notify(capacity);
            return;
        }
        if (measurement) {
            this.#pendingExpansion = { measurement, capacity };
            this.#expand();
        }
    }

    #commitExpansion = (): void => {
        const pending = this.#pendingExpansion;
        this.#pendingExpansion = null;
        if (!pending || !this.#root) return;
        try {
            const measurement = this.#readMeasurement();
            const capacity = measurement ? resolvePaneCapacity(measurement, this.#lastCapacity) : null;
            if (measurement && capacity === pending.capacity && sameMeasurement(measurement, pending.measurement)) {
                this.#measurement = measurement;
                this.#lastCapacity = capacity;
                this.#failure = null;
                this.#notify(capacity);
            } else this.#applyMeasurement(measurement);
        } catch (error) {
            this.#fail(ensureError(error));
        }
    };

    #scheduleMeasurement = (): void => {
        if (!this.#root || this.#frame !== null) return;
        this.#expand.cancel();
        this.#pendingExpansion = null;
        this.#frame = this.#resources.requestAnimationFrame(() => {
            this.#frame = null;
            this.refresh();
        });
    };

    #cancelPending(): void {
        this.#expand.cancel();
        this.#pendingExpansion = null;
        if (this.#frame !== null) this.#resources.cancelAnimationFrame(this.#frame);
        this.#frame = null;
    }

    #notify(capacity: PaneCapacity | null): void {
        try {
            this.#onChange(capacity);
        } catch (error) {
            errorHandler.error('PagePaneGeometry', 'Capacity observer failed', ensureError(error));
        }
    }

    #fail(error: Error): void {
        const previous = this.getCapacity();
        this.#measurement = null;
        if (previous !== null) this.#notify(null);
        const reportFailure = this.#failure === null;
        this.#failure = error;
        if (reportFailure) this.#onFailure(error);
    }
}

export { PagePaneGeometry };
