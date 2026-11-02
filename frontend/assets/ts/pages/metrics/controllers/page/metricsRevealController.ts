/* SoAI - Metrics page reveal and pane visibility presentation hold [frontend/assets/ts/pages/metrics/controllers/page/metricsRevealController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class MetricsRevealController {
    #held = true;
    #dirty = false;
    #visible = true;

    prepare(): void {
        this.#held = false;
        this.#dirty = false;
    }

    hold(): void {
        this.#held = true;
        this.#dirty = false;
    }

    requestRefresh(): boolean {
        if (!this.#held && this.#visible) {
            return true;
        }
        this.#dirty = true;
        return false;
    }

    release(): boolean {
        if (!this.#held) {
            return false;
        }
        this.#held = false;
        return this.#takePendingRefresh();
    }

    setVisible(visible: boolean): boolean {
        if (this.#visible === visible) return false;
        this.#visible = visible;
        return this.#takePendingRefresh();
    }

    #takePendingRefresh(): boolean {
        if (this.#held || !this.#visible) return false;
        const dirty = this.#dirty;
        this.#dirty = false;
        return dirty;
    }

    cancel(): void {
        this.#held = true;
        this.#dirty = false;
    }
}

export { MetricsRevealController };
