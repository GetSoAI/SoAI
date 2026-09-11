/* SoAI - Image viewer touch paging and dismissal [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerPaging.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import { resistImageDisplacement, type Point } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import type { ContentPreviewImageNavigationDirection } from '@core/ui/modals/contentpreview/types.ts';

type ImageViewerGestureActions = Readonly<{
    canNavigate: () => boolean;
    isBlocked: () => boolean;
    requestNavigation: (direction: ContentPreviewImageNavigationDirection, offset: number) => void;
    requestClose: () => void;
}>;
type ImageViewerPagingMode = 'page' | 'dismiss';

const createContentPreviewImageViewerPaging = (refs: ContentPreviewImageViewerRefs, resources: ResourceTracker, actions: ImageViewerGestureActions) => {
    let offset: Point = { x: 0, y: 0 };
    let frame: number | null = null;

    const present = (point: Point): void => {
        offset = point;
        refs.scene.style.transform = `translate3d(${point.x}px, ${point.y}px, 0)`;
    };

    const cancel = (): void => {
        if (frame !== null) {
            resources.cancelAnimationFrame(frame);
            frame = null;
        }
    };

    const reset = (immediate = false): void => {
        cancel();
        if (immediate || prefersReducedMotion(refs.viewport)) {
            present({ x: 0, y: 0 });
            return;
        }
        const initial = offset;
        const startedAt = performance.now();
        const advance = (timestamp: number): void => {
            frame = null;
            const progress = prefersReducedMotion(refs.viewport) ? 1 : Math.min(1, (timestamp - startedAt) / 360);
            const remaining = progress >= 1 ? 0 : Math.exp(-8 * progress) * (Math.cos(10 * progress) + 0.8 * Math.sin(10 * progress));
            present({ x: initial.x * remaining, y: initial.y * remaining });
            if (progress < 1) {
                frame = resources.requestAnimationFrame(advance);
            }
        };
        frame = resources.requestAnimationFrame(advance);
    };

    const drag = (mode: ImageViewerPagingMode, delta: Point): void => {
        cancel();
        if (mode === 'page') {
            present({ x: actions.canNavigate() ? delta.x : resistImageDisplacement(delta.x, refs.viewport.clientWidth), y: 0 });
        } else {
            present({ x: 0, y: delta.y > 0 ? delta.y : resistImageDisplacement(delta.y, refs.viewport.clientHeight) });
        }
    };

    const finish = (mode: ImageViewerPagingMode, delta: Point, elapsed: number): void => {
        const duration = Math.max(1, elapsed);
        if (mode === 'page' && actions.canNavigate() && (Math.abs(delta.x) >= Math.max(56, refs.viewport.clientWidth * 0.16) || (Math.abs(delta.x) >= 24 && Math.abs(delta.x) / duration >= 0.5))) {
            actions.requestNavigation(delta.x < 0 ? 'next' : 'previous', offset.x);
        } else if (mode === 'dismiss' && delta.y > 0 && (delta.y >= Math.max(80, refs.viewport.clientHeight * 0.14) || (delta.y >= 32 && delta.y / duration >= 0.55))) {
            actions.requestClose();
        } else {
            reset();
        }
    };

    return Object.freeze({ drag, finish, reset, cancel });
};

export { createContentPreviewImageViewerPaging };
export type { ImageViewerGestureActions };
