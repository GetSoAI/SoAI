/* SoAI - Chat attach modal browse abort wiring [frontend/assets/ts/pages/chat/controllers/modals/chatattach/chatAttachBrowseAbortController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const createBrowseAbortController = (parentSignal: AbortSignal): AbortController => {
    const controller = new AbortController();
    if (parentSignal.aborted) {
        controller.abort(parentSignal.reason);
        return controller;
    }
    const abortController = (): void => {
        controller.abort(parentSignal.reason);
    };
    parentSignal.addEventListener('abort', abortController, { once: true, signal: controller.signal });
    return controller;
};

const releaseBrowseAbortController = (controller: AbortController): void => {
    if (!controller.signal.aborted) {
        controller.abort();
    }
};

type BrowseAbortControllerRegistry = Set<AbortController>;

const createTrackedBrowseAbortController = (registry: BrowseAbortControllerRegistry, parentSignal: AbortSignal): AbortController => {
    const controller = createBrowseAbortController(parentSignal);
    registry.add(controller);
    return controller;
};

const releaseTrackedBrowseAbortController = (registry: BrowseAbortControllerRegistry, controller: AbortController): void => {
    registry.delete(controller);
    releaseBrowseAbortController(controller);
};

const abortTrackedBrowseAbortControllers = (registry: BrowseAbortControllerRegistry): void => {
    const controllers = [...registry];
    registry.clear();
    for (const controller of controllers) {
        releaseBrowseAbortController(controller);
    }
};

export { abortTrackedBrowseAbortControllers, createTrackedBrowseAbortController, releaseTrackedBrowseAbortController };
export type { BrowseAbortControllerRegistry };
