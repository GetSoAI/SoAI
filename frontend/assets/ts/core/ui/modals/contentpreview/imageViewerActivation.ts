/* SoAI - Content preview image viewer activation animation [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerActivation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ContentPreviewImageViewerMotion } from '@core/ui/modals/contentpreview/imageViewerMotion.ts';
import type { Point } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import type { ContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerStateTypes.ts';

type MountArguments = Readonly<{
    state: ContentPreviewImageViewerState;
    motion: ContentPreviewImageViewerMotion;
}>;

const createContentPreviewImageViewerActivation = ({ state, motion }: MountArguments) => {
    let lastTouchActivation = -Infinity;
    let lastTap: Readonly<{ time: number; point: Point }> | null = null;

    const triggerDoubleActivation = (center: Point): void => {
        const transform = state.getTransform();
        const fitScale = state.getGeometry().fitScale;
        const nativeTarget = fitScale >= 0.999 ? 2 : 1;
        const target = Math.abs(transform.scale - nativeTarget) <= 0.001 ? fitScale : nativeTarget;
        motion.zoomAt(target, center, 460);
    };

    const tap = (point: Point): void => {
        const now = performance.now();
        if (lastTap && now - lastTap.time <= 300 && Math.hypot(point.x - lastTap.point.x, point.y - lastTap.point.y) <= 12) {
            lastTap = null;
            lastTouchActivation = now;
            triggerDoubleActivation(point);
            return;
        }
        lastTap = { time: now, point };
    };

    return Object.freeze({
        tap,
        clearTap: (): void => {
            lastTap = null;
        },
        doubleClick: (point: Point): void => {
            if (performance.now() - lastTouchActivation > 500) {
                triggerDoubleActivation(point);
            }
        }
    });
};

export { createContentPreviewImageViewerActivation };
