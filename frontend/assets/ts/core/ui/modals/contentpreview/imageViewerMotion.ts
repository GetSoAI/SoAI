/* SoAI - Image viewer kinetic motion and elastic settlement [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { prefersReducedMotion } from '@core/animations/prefersReducedMotion.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { CONTENT_PREVIEW_IMAGE_MAX_SCALE, resistImageDisplacement, resolveViewerOffsets, type Point } from '@core/ui/modals/contentpreview/imageViewerGeometry.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import type { ContentPreviewImageViewerState } from '@core/ui/modals/contentpreview/imageViewerStateTypes.ts';

type MotionTransform = Readonly<{ scale: number; offsetX: number; offsetY: number }>;
type KineticAxis = Readonly<{ position: number; velocity: number }>;

const advanceKineticAxis = (position: number, velocity: number, minimum: number, maximum: number, elapsed: number): KineticAxis => {
    const target = clampNumber(position, minimum, maximum);
    if (position !== target) {
        const frequency = 0.022;
        const displacement = position - target;
        const coefficient = velocity + frequency * displacement;
        const decay = Math.exp(-frequency * elapsed);
        return { position: target + (displacement + coefficient * elapsed) * decay, velocity: (velocity - frequency * coefficient * elapsed) * decay };
    }
    const friction = -Math.log(0.9) / 16.67;
    const decay = Math.exp(-friction * elapsed);
    return { position: position + (velocity * (1 - decay)) / friction, velocity: velocity * decay };
};

const createContentPreviewImageViewerMotion = (refs: ContentPreviewImageViewerRefs, state: ContentPreviewImageViewerState, resources: ResourceTracker) => {
    let animationFrame: number | null = null;

    const cancel = (): void => {
        if (animationFrame !== null) {
            resources.cancelAnimationFrame(animationFrame);
            animationFrame = null;
        }
        refs.stage.classList.remove('is-animating');
    };

    const constrain = (transform: MotionTransform): MotionTransform => {
        const geometry = state.getGeometry();
        const scale = clampNumber(transform.scale, geometry.fitScale, CONTENT_PREVIEW_IMAGE_MAX_SCALE);
        const offsets = resolveViewerOffsets(geometry.imageWidth, geometry.imageHeight, geometry.viewportWidth, geometry.viewportHeight, scale, transform.offsetX, transform.offsetY);
        return { scale, offsetX: offsets.x, offsetY: offsets.y };
    };

    const animateTo = (requested: MotionTransform, duration = 360): void => {
        cancel();
        const target = constrain(requested);
        const initial = state.getTransform();
        if (prefersReducedMotion(refs.viewport)) {
            state.applyTransform(target.scale, target.offsetX, target.offsetY, true);
            return;
        }
        const startedAt = performance.now();
        refs.stage.classList.add('is-animating');
        const advance = (timestamp: number): void => {
            animationFrame = null;
            const progress = Math.min(1, (timestamp - startedAt) / duration);
            if (progress >= 1 || prefersReducedMotion(refs.viewport)) {
                state.applyTransform(target.scale, target.offsetX, target.offsetY, true);
                refs.stage.classList.remove('is-animating');
                state.scheduleMinimapHide(900);
                return;
            }
            const remaining = Math.exp(-8 * progress) * (Math.cos(10 * progress) + 0.8 * Math.sin(10 * progress));
            const geometry = state.getGeometry();
            const scale = clampNumber(target.scale + (initial.scale - target.scale) * remaining, geometry.fitScale * 0.84, CONTENT_PREVIEW_IMAGE_MAX_SCALE * 1.08);
            state.applyTransform(scale, target.offsetX + (initial.offsetX - target.offsetX) * remaining, target.offsetY + (initial.offsetY - target.offsetY) * remaining, true, true);
            animationFrame = resources.requestAnimationFrame(advance);
        };
        animationFrame = resources.requestAnimationFrame(advance);
    };

    const zoomAt = (scale: number, center: Point, duration = 360): void => {
        const initial = state.getTransform();
        const contentX = (center.x - initial.offsetX) / initial.scale;
        const contentY = (center.y - initial.offsetY) / initial.scale;
        animateTo({ scale, offsetX: center.x - contentX * scale, offsetY: center.y - contentY * scale }, duration);
    };

    const settle = (center?: Point): void => {
        const initial = state.getTransform();
        const geometry = state.getGeometry();
        const scale = clampNumber(initial.scale, geometry.fitScale, CONTENT_PREVIEW_IMAGE_MAX_SCALE);
        if (center && scale !== initial.scale) {
            zoomAt(scale, center);
            return;
        }
        const target = constrain(initial);
        if (target.scale !== initial.scale || target.offsetX !== initial.offsetX || target.offsetY !== initial.offsetY) {
            animateTo(target);
        }
    };

    const pan = (offsetX: number, offsetY: number, elastic: boolean): void => {
        const scale = state.getTransform().scale;
        const geometry = state.getGeometry();
        const offsets = resolveViewerOffsets(geometry.imageWidth, geometry.imageHeight, geometry.viewportWidth, geometry.viewportHeight, scale, offsetX, offsetY);
        const bounded = { offsetX: offsets.x, offsetY: offsets.y };
        state.applyTransform(scale, elastic ? bounded.offsetX + resistImageDisplacement(offsetX - bounded.offsetX, geometry.viewportWidth) : bounded.offsetX, elastic ? bounded.offsetY + resistImageDisplacement(offsetY - bounded.offsetY, geometry.viewportHeight) : bounded.offsetY, true, elastic);
    };

    const inertia = (releaseVelocity: Point): void => {
        cancel();
        if (prefersReducedMotion(refs.viewport)) {
            const target = constrain(state.getTransform());
            state.applyTransform(target.scale, target.offsetX, target.offsetY, true);
            return;
        }
        let velocityX = clampNumber(releaseVelocity.x, -1.4, 1.4);
        let velocityY = clampNumber(releaseVelocity.y, -1.4, 1.4);
        const startedAt = performance.now();
        let previousTime = startedAt;
        const advance = (timestamp: number): void => {
            animationFrame = null;
            const elapsed = clampNumber(timestamp - previousTime, 0, 32);
            previousTime = timestamp;
            const transform = state.getTransform();
            const geometry = state.getGeometry();
            const minimum = resolveViewerOffsets(geometry.imageWidth, geometry.imageHeight, geometry.viewportWidth, geometry.viewportHeight, transform.scale, -Infinity, -Infinity);
            const maximum = resolveViewerOffsets(geometry.imageWidth, geometry.imageHeight, geometry.viewportWidth, geometry.viewportHeight, transform.scale, Infinity, Infinity);
            const horizontal = advanceKineticAxis(transform.offsetX, velocityX, minimum.x, maximum.x, elapsed);
            const vertical = advanceKineticAxis(transform.offsetY, velocityY, minimum.y, maximum.y, elapsed);
            velocityX = horizontal.velocity;
            velocityY = vertical.velocity;
            const offsetX = clampNumber(horizontal.position, minimum.x - geometry.viewportWidth * 0.15, maximum.x + geometry.viewportWidth * 0.15);
            const offsetY = clampNumber(vertical.position, minimum.y - geometry.viewportHeight * 0.15, maximum.y + geometry.viewportHeight * 0.15);
            const target = constrain({ scale: transform.scale, offsetX, offsetY });
            if (timestamp - startedAt >= 2000 || prefersReducedMotion(refs.viewport) || (Math.hypot(velocityX, velocityY) < 0.02 && Math.hypot(offsetX - target.offsetX, offsetY - target.offsetY) < 0.1)) {
                state.applyTransform(target.scale, target.offsetX, target.offsetY, true);
                state.scheduleMinimapHide(900);
                return;
            }
            state.applyTransform(transform.scale, offsetX, offsetY, true, true);
            animationFrame = resources.requestAnimationFrame(advance);
        };
        animationFrame = resources.requestAnimationFrame(advance);
    };

    return Object.freeze({ cancel, animateTo, zoomAt, settle, pan, inertia });
};

type ContentPreviewImageViewerMotion = ReturnType<typeof createContentPreviewImageViewerMotion>;

export { createContentPreviewImageViewerMotion, advanceKineticAxis };
export type { ContentPreviewImageViewerMotion };
