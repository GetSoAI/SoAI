/* SoAI - Content preview image viewer activation animation [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerActivation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import type { ContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerStateTypes.ts';

type MountArguments = Readonly<{
    refs: ContentPreviewImageViewerRefs;
    state: ContentPreviewImageViewerState;
    resources: ResourceTracker;
}>;

type Point = Readonly<{ x: number; y: number }>;

type ContentPreviewImageViewerActivation = Readonly<{
    triggerDoubleActivation: (center: Point) => void;
    cancel: () => void;
}>;

const createContentPreviewImageViewerActivation = ({ refs, state, resources }: MountArguments): ContentPreviewImageViewerActivation => {
    let animationFrame: number | null = null;
    let finalizeTimer: number | null = null;

    const cancel = (): void => {
        if (animationFrame !== null) {
            resources.cancelAnimationFrame(animationFrame);
            animationFrame = null;
        }
        if (finalizeTimer !== null) {
            resources.clearTimeout(finalizeTimer);
            finalizeTimer = null;
        }
        refs.stage.classList.remove('is-animating');
    };

    const triggerDoubleActivation = (center: Point): void => {
        cancel();
        const transform = state.getTransform();
        const targetFitMode = transform.fitMode || transform.scale < 0.999 || transform.scale > 1.001;

        refs.stage.classList.add('is-animating');

        animationFrame = resources.requestAnimationFrame(() => {
            animationFrame = resources.requestAnimationFrame(() => {
                animationFrame = null;
                if (targetFitMode) {
                    state.centerNativeAt(false, center);
                } else {
                    state.fitToViewportAt(false, center);
                }
                finalizeTimer = resources.setTimeout(() => {
                    finalizeTimer = null;
                    refs.stage.classList.remove('is-animating');
                }, 460);
            });
        });
    };

    return Object.freeze({
        triggerDoubleActivation,
        cancel
    });
};

export { createContentPreviewImageViewerActivation };
export type { ContentPreviewImageViewerActivation };
