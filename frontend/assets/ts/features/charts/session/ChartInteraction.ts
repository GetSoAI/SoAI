/* SoAI - Chart interaction lifecycle ownership [frontend/assets/ts/features/charts/session/ChartInteraction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LifecycleResources } from '@core/lifecyclemodel/LifecycleResources.ts';
import { setupEventListeners } from '@features/charts/effects/events.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';

class ChartInteraction {
    readonly #scene: ChartInteractionScene;
    readonly #resources = new LifecycleResources();
    #active = false;

    constructor(scene: ChartInteractionScene) {
        this.#scene = scene;
    }

    initialize(signal: AbortSignal): void {
        signal.throwIfAborted();
        if (this.#active) return;
        this.#active = true;
        setupEventListeners(this.#scene, (target, event, handler, options) => {
            this.#resources.addEventListener(target, event, handler, options);
        });
    }

    async destroy(): Promise<void> {
        if (!this.#active) return;
        this.#active = false;
        await this.#resources.cleanup();
        this.#scene.interaction.pointer.activePointers.clear();
        this.#scene.interaction.pointer.nativeScrollPointerIds.clear();
        this.#scene.interaction.pointer.primaryId = null;
        this.#scene.interaction.pointer.pinch = null;
        this.#scene.interaction.pointer.lastTap = null;
        this.#scene.interaction.wheelPayload = null;
        this.#scene.interaction.wheelPending = false;
    }
}

export { ChartInteraction };
