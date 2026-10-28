/* SoAI - Offscreen visualization worker entrypoint [frontend/assets/ts/app/entrypoints/visualization/visualizationWorker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { VisualizationRuntime } from '@core/visualization/VisualizationRuntime.ts';
import type { VisualizationRequest } from '@core/visualization/protocol.ts';

const runtime = new VisualizationRuntime({
    post: (response) => globalThis.postMessage(response),
    requestFrame: (callback) => requestAnimationFrame(callback),
    cancelFrame: (identifier) => cancelAnimationFrame(identifier),
    now: () => performance.now()
});

globalThis.onmessage = (event: MessageEvent<VisualizationRequest | null>): void => runtime.receive(event.data);
