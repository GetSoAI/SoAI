/* SoAI - Metrics page reveal presentation hold [frontend/assets/ts/pages/metrics/controllers/page/metricsRevealController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class MetricsRevealController {
    #held = true;
    #dirty = false;

    prepare(): void {
        this.#held = false;
        this.#dirty = false;
    }

    hold(): void {
        this.#held = true;
        this.#dirty = false;
    }

    requestRefresh(): boolean {
        if (!this.#held) {
            return true;
        }
        this.#dirty = true;
        return false;
    }

    release(): boolean {
        if (!this.#held) {
            return false;
        }
        const dirty = this.#dirty;
        this.#held = false;
        this.#dirty = false;
        return dirty;
    }

    cancel(): void {
        this.#held = true;
        this.#dirty = false;
    }
}

export { MetricsRevealController };
