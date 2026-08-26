/* SoAI - Shared animations speed [frontend/assets/ts/core/animations/speed.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDocumentElement } from '@core/environment/public.ts';

type AnimationSpeed = 'normal' | 'fast';

const ANIMATION_SPEED_ATTRIBUTE = 'data-animation-speed';
const ANIMATION_SPEED_STORAGE_KEY = 'soai.ui.animation_speed';
const DEFAULT_ANIMATION_SPEED: AnimationSpeed = 'normal';
const FAST_ANIMATION_SPEED_FACTOR = 0.5;
const DOCUMENT_NODE_TYPE = 9;
const REDUCED_MOTION_MEDIA_QUERY = '(prefers-reduced-motion: reduce)';

const isAnimationSpeed = <T>(value: T): value is T & AnimationSpeed => value === 'normal' || value === 'fast';

const isDocumentScope = (scope: Document | Element): scope is Document => scope.nodeType === DOCUMENT_NODE_TYPE;

const resolveAnimationSpeed = <T>(value: T): AnimationSpeed => (isAnimationSpeed(value) ? value : DEFAULT_ANIMATION_SPEED);

const resolveAnimationSpeedFromRoot = (root: Element): AnimationSpeed => resolveAnimationSpeed(root.getAttribute(ANIMATION_SPEED_ATTRIBUTE));

const resolveDocumentFromScope = (scope: Document | Element | null | undefined): Document => {
    if (!scope) {
        return getDocumentElement().ownerDocument;
    }
    if (isDocumentScope(scope)) {
        return scope;
    }
    return scope.ownerDocument;
};

const resolveAnimationSpeedFromScope = (scope: Document | Element | null | undefined): AnimationSpeed => {
    const documentRef = resolveDocumentFromScope(scope);
    return resolveAnimationSpeedFromRoot(documentRef.documentElement);
};

const isReducedAnimationScope = (scope: Document | Element | null | undefined): boolean => {
    const documentRef = resolveDocumentFromScope(scope);
    const root = documentRef.documentElement;
    if (root.getAttribute('data-transition-level') === 'none' || documentRef.body?.classList.contains('reduce-motions')) {
        return true;
    }
    const view = documentRef.defaultView;
    if (view && typeof view.matchMedia === 'function' && view.matchMedia(REDUCED_MOTION_MEDIA_QUERY).matches) {
        return true;
    }
    return false;
};

const scaleAnimationDurationMs = (baseDurationMs: number, scope?: Document | Element | null): number => {
    if (!Number.isFinite(baseDurationMs) || baseDurationMs <= 0 || isReducedAnimationScope(scope)) {
        return 0;
    }
    const speed = resolveAnimationSpeedFromScope(scope);
    const factor = speed === 'fast' ? FAST_ANIMATION_SPEED_FACTOR : 1;
    return Math.max(0, Math.round(baseDurationMs * factor));
};

export { ANIMATION_SPEED_ATTRIBUTE, ANIMATION_SPEED_STORAGE_KEY, DEFAULT_ANIMATION_SPEED, isAnimationSpeed, isReducedAnimationScope, resolveAnimationSpeed, resolveAnimationSpeedFromRoot, resolveAnimationSpeedFromScope, scaleAnimationDurationMs };
export type { AnimationSpeed };
