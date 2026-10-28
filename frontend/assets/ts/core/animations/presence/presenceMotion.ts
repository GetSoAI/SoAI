/* SoAI - Presence motion keyframes for appearing, disappearing and resizing controls [frontend/assets/ts/core/animations/presence/presenceMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measurePresenceGeometry, parsePixels, readComputedStyle, resolveAxisProperties, type PresenceGeometry } from '@core/animations/presence/presenceGeometry.ts';
import { canAnimatePresence, isPresenceAtomic } from '@core/animations/presence/presenceEligibility.ts';
import { dom } from '@core/dom/dom.ts';
import { MODAL_ROOT_CLASS } from '@core/modals/guards.ts';
import { readPresenceTokens, type PresenceTokens } from '@core/animations/presence/presenceTokens.ts';

interface PresenceFrame {
    visual: PresenceKeyframe;
    layout: PresenceKeyframe | null;
}

interface PresenceSize {
    width: number;
    height: number;
}

interface PresenceExitOptions {
    fromOpacity?: number;
}

type PresenceKeyframe = Record<string, string | number>;

type PresencePhase = 'enter' | 'exit' | 'morph';

const runningPresenceAnimations = new Map<Element, { animation: Animation; phase: PresencePhase }>();

const canAnimate = (element: HTMLElement): boolean => typeof element.animate === 'function';

const trackPresenceAnimation = (element: HTMLElement, animation: Animation, phase: PresencePhase): Animation => {
    const windowRef = element.ownerDocument.defaultView;
    if (windowRef === null) throw new Error('Presence animations require an owning window');
    animation.startTime = windowRef.performance.now();
    runningPresenceAnimations.set(element, { animation, phase });
    const forget = (): void => {
        if (runningPresenceAnimations.get(element)?.animation === animation) {
            runningPresenceAnimations.delete(element);
        }
    };
    animation.addEventListener('finish', forget, { once: true });
    animation.addEventListener('cancel', forget, { once: true });
    return animation;
};

const isPresenceAnimating = (element: Element): boolean => runningPresenceAnimations.has(element);

const hasPresenceAnimationInSubtree = (root: Element): boolean => {
    for (const animatedElement of runningPresenceAnimations.keys()) {
        if (root.contains(animatedElement)) return true;
    }
    return false;
};

const deferUntilPresenceExitsSettle = (element: Element, complete: () => void): boolean => {
    const pending = new Set<Animation>();
    for (let ancestor: Element | null = element; ancestor !== null; ancestor = ancestor.parentElement) {
        const record = runningPresenceAnimations.get(ancestor);
        if (record?.phase === 'exit') pending.add(record.animation);
    }
    if (pending.size === 0) return false;
    for (const animation of pending) {
        const settle = (): void => {
            animation.removeEventListener('finish', settle);
            animation.removeEventListener('cancel', settle);
            pending.delete(animation);
            if (pending.size === 0) complete();
        };
        animation.addEventListener('finish', settle);
        animation.addEventListener('cancel', settle);
    }
    return true;
};

const isPresenceMorphing = (element: Element): boolean => runningPresenceAnimations.get(element)?.phase === 'morph';

const finishPresenceAnimations = (root: Document | Element): void => {
    for (const [element, record] of runningPresenceAnimations) {
        if (root.contains(element) || root === element.ownerDocument) {
            record.animation.finish();
        }
    }
};

const stopPresenceAnimation = (element: Element): void => {
    const animation = runningPresenceAnimations.get(element)?.animation;
    runningPresenceAnimations.delete(element);
    animation?.cancel();
};

const captureLayoutFrame = (style: CSSStyleDeclaration, geometry: PresenceGeometry | null): PresenceKeyframe | null => {
    if (!geometry) {
        return null;
    }
    return Object.fromEntries(Object.values(resolveAxisProperties(geometry.axis)).map((property) => [property, style[property]]));
};
const interruptPresenceAnimation = (element: HTMLElement, tokens: PresenceTokens): PresenceFrame | null => {
    const animation = runningPresenceAnimations.get(element)?.animation;
    const style = animation ? readComputedStyle(element) : null;
    if (!animation || !style) {
        animation?.cancel();
        return null;
    }
    const visual: PresenceKeyframe = { opacity: style.opacity };
    if (tokens.scaleFrom !== 1) visual['scale'] = style.scale;
    if (tokens.blurFrom !== '0px' && tokens.blurFrom !== '0') visual['filter'] = style.filter;
    if (tokens.translateFrom) visual['translate'] = style.translate;
    const frame = {
        visual,
        layout: captureLayoutFrame(style, measurePresenceGeometry(element))
    };
    stopPresenceAnimation(element);
    return frame;
};
const buildHiddenVisualKeyframe = (tokens: PresenceTokens): PresenceKeyframe => {
    const keyframe: PresenceKeyframe = { opacity: 0 };
    if (tokens.scaleFrom !== 1) keyframe['scale'] = tokens.scaleFrom;
    if (tokens.blurFrom !== '0px' && tokens.blurFrom !== '0') keyframe['filter'] = `blur(${tokens.blurFrom})`;
    if (tokens.translateFrom) keyframe['translate'] = tokens.translateFrom;
    return keyframe;
};

const CONTROL_SELECTOR = "button, [role='button']";
const VISUAL_ONLY_ATTRIBUTE = 'data-presence-visual-only';

const resolveVisualTargets = (element: HTMLElement): HTMLElement[] => {
    if (element.matches(CONTROL_SELECTOR) || element.classList.contains(MODAL_ROOT_CLASS) || isPresenceAtomic(element)) {
        return [element];
    }
    const controls = dom.resolveAll(CONTROL_SELECTOR, element).filter((target): target is HTMLElement => target instanceof HTMLElement && target.getClientRects().length > 0);
    return controls.length ? controls : [element];
};

const buildLayoutKeyframes = (element: HTMLElement, geometry: PresenceGeometry | null, visualOnly: boolean): { collapsed: PresenceKeyframe; expanded: PresenceKeyframe } => {
    if (!geometry || visualOnly) {
        return { collapsed: {}, expanded: {} };
    }
    const properties = resolveAxisProperties(geometry.axis);
    const style = readComputedStyle(element);
    if (!style) {
        return { collapsed: {}, expanded: {} };
    }
    const marginStart = parsePixels(style[properties.marginStart]);
    const marginEnd = parsePixels(style[properties.marginEnd]);
    const padding = parsePixels(style[properties.paddingStart]) + parsePixels(style[properties.paddingEnd]);
    const border = parsePixels(style[properties.borderStart]) + parsePixels(style[properties.borderEnd]);
    const outerSize = geometry.size + (style.boxSizing === 'border-box' ? 0 : padding + border);
    const gap = geometry.gapSide ? geometry.gap : 0;
    const margin = geometry.gapSide === 'start' ? properties.marginStart : properties.marginEnd;
    const otherMargin = geometry.gapSide === 'start' ? marginEnd : marginStart;
    return {
        collapsed: { flexShrink: 0, [properties.size]: `${geometry.size}px`, [margin]: `${-outerSize - otherMargin - gap}px` },
        expanded: { flexShrink: 0, [properties.size]: `${geometry.size}px` }
    };
};

const preparePresenceEnter = (element: HTMLElement, visualOnly = false): (() => Animation | null) => {
    if (!canAnimatePresence(element)) {
        return () => {
            stopPresenceAnimation(element);
            return null;
        };
    }
    const tokens = readPresenceTokens(element);
    const targets = resolveVisualTargets(element);
    const ownsVisual = targets.includes(element);
    const children = ownsVisual ? [] : targets.map((target) => preparePresenceEnter(target, true));
    const frame = interruptPresenceAnimation(element, tokens);
    const useVisualOnly = visualOnly || element.hasAttribute(VISUAL_ONLY_ATTRIBUTE);
    const layout = buildLayoutKeyframes(element, useVisualOnly ? null : measurePresenceGeometry(element), useVisualOnly);
    const from = { ...layout.collapsed, ...frame?.layout, ...(ownsVisual ? (frame?.visual ?? buildHiddenVisualKeyframe(tokens)) : {}) };
    return () => {
        children.forEach((start) => start());
        if (tokens.enterDurationMs <= 0 || !canAnimate(element)) {
            return null;
        }
        const animation = element.animate([from, layout.expanded], { duration: tokens.enterDurationMs, easing: tokens.enterEasing, fill: 'backwards' });
        return trackPresenceAnimation(element, animation, 'enter');
    };
};

const validatePresenceExitOptions = (options: PresenceExitOptions): void => {
    if (options.fromOpacity !== undefined && (!Number.isFinite(options.fromOpacity) || options.fromOpacity < 0 || options.fromOpacity > 1)) throw new Error('Presence exit opacity must be finite and between zero and one.');
};

const animatePresenceExit = (element: HTMLElement, visualOnly = false, options: PresenceExitOptions = {}): Animation | null => {
    validatePresenceExitOptions(options);
    const tokens = readPresenceTokens(element);
    const frame = interruptPresenceAnimation(element, tokens);
    if (tokens.exitDurationMs <= 0 || !canAnimate(element) || !canAnimatePresence(element)) {
        return null;
    }
    const targets = resolveVisualTargets(element);
    const ownsVisual = targets.includes(element);
    const useVisualOnly = visualOnly || element.hasAttribute(VISUAL_ONLY_ATTRIBUTE);
    const layout = buildLayoutKeyframes(element, useVisualOnly ? null : measurePresenceGeometry(element), useVisualOnly);
    const from = { ...layout.expanded, ...frame?.layout, ...(ownsVisual ? frame?.visual : {}) };
    if (ownsVisual && options.fromOpacity !== undefined) from['opacity'] = options.fromOpacity;
    const to = { ...layout.collapsed, ...(ownsVisual ? buildHiddenVisualKeyframe(tokens) : {}) };
    const animation = element.animate([from, to], { duration: tokens.exitDurationMs, easing: tokens.exitEasing, fill: 'both' });
    trackPresenceAnimation(element, animation, 'exit');
    if (!ownsVisual) {
        targets.forEach((target) => {
            if (runningPresenceAnimations.get(target)?.phase !== 'exit') {
                const childAnimation = animatePresenceExit(target, true);
                const cancelChildExit = (): void => {
                    childAnimation?.cancel();
                };
                animation.addEventListener('cancel', cancelChildExit, { once: true });
            }
        });
    }
    return animation;
};

const measurePresenceSize = (element: HTMLElement): PresenceSize | null => {
    const style = readComputedStyle(element);
    if (!style || style.display === 'none') {
        return null;
    }
    const size = { width: parsePixels(style.width), height: parsePixels(style.height) };
    return size.width > 0 && size.height > 0 ? size : null;
};

const MORPH_THRESHOLD_PX = 0.5;
const CLIP_KEYFRAME: PresenceKeyframe = { overflow: 'clip' };

const animatePresenceMorph = (element: HTMLElement, from: PresenceSize, to: PresenceSize, options: { fadeChildren?: boolean; preserveWrapping?: boolean; preserveChildInlineSize?: boolean; afterExitOf?: Element } = {}): Animation | null => {
    const tokens = readPresenceTokens(element);
    const widthChanged = Math.abs(from.width - to.width) > MORPH_THRESHOLD_PX;
    const heightChanged = Math.abs(from.height - to.height) > MORPH_THRESHOLD_PX;
    if ((!widthChanged && !heightChanged) || tokens.morphDurationMs <= 0 || !canAnimate(element) || !canAnimatePresence(element, { allowAtomicMorph: true }) || isPresenceAnimating(element)) {
        return null;
    }
    const start: PresenceKeyframe = { ...CLIP_KEYFRAME };
    const end: PresenceKeyframe = { ...CLIP_KEYFRAME };
    if (options.preserveWrapping !== true) {
        start['whiteSpace'] = 'nowrap';
        end['whiteSpace'] = 'nowrap';
    }
    if (widthChanged) {
        start['minWidth'] = end['minWidth'] = '0px';
        start['width'] = `${from.width}px`;
        end['width'] = `${to.width}px`;
    }
    if (heightChanged) {
        start['minHeight'] = end['minHeight'] = '0px';
        start['height'] = `${from.height}px`;
        end['height'] = `${to.height}px`;
    }
    const animationOptions: KeyframeAnimationOptions = { duration: tokens.morphDurationMs, easing: tokens.enterEasing, fill: 'backwards' };
    const retainedChildAnimations: Animation[] = [];
    if (options.fadeChildren !== false || options.preserveChildInlineSize === true) {
        for (const child of Array.from(element.children)) {
            if (!(child instanceof HTMLElement) || !canAnimate(child) || !canAnimatePresence(child)) continue;
            const firstFrame: PresenceKeyframe = {};
            const lastFrame: PresenceKeyframe = {};
            if (widthChanged && options.preserveChildInlineSize === true) {
                const size = measurePresenceSize(child);
                if (size !== null) {
                    firstFrame['minInlineSize'] = lastFrame['minInlineSize'] = `${size.width}px`;
                    firstFrame['inlineSize'] = lastFrame['inlineSize'] = `${size.width}px`;
                }
            }
            if (options.fadeChildren !== false) firstFrame['opacity'] = isPresenceMorphing(child) ? (readComputedStyle(child)?.opacity ?? tokens.morphFadeFrom) : tokens.morphFadeFrom;
            if (Object.keys(firstFrame).length === 0) continue;
            stopPresenceAnimation(child);
            retainedChildAnimations.push(trackPresenceAnimation(child, child.animate([firstFrame, lastFrame], animationOptions), 'morph'));
        }
    }
    const animation = trackPresenceAnimation(element, element.animate([start, end], animationOptions), 'morph');
    if (options.preserveChildInlineSize === true && retainedChildAnimations.length > 0) {
        const releaseChildren = (): void => {
            animation.removeEventListener('finish', releaseChildren);
            animation.removeEventListener('cancel', releaseChildren);
            retainedChildAnimations.forEach((childAnimation) => childAnimation.cancel());
        };
        animation.addEventListener('finish', releaseChildren);
        animation.addEventListener('cancel', releaseChildren);
    }
    if (
        options.afterExitOf !== undefined &&
        deferUntilPresenceExitsSettle(options.afterExitOf, () => {
            if (runningPresenceAnimations.get(element)?.animation !== animation) return;
            if (element.isConnected) {
                if (options.preserveChildInlineSize === true) retainedChildAnimations.forEach((childAnimation) => childAnimation.play());
                animation.play();
            } else stopPresenceAnimation(element);
        })
    ) {
        animation.pause();
        animation.currentTime = 0;
        if (options.preserveChildInlineSize === true) {
            retainedChildAnimations.forEach((childAnimation) => {
                childAnimation.pause();
                childAnimation.currentTime = 0;
            });
        }
    }
    return animation;
};

export { animatePresenceExit, animatePresenceMorph, deferUntilPresenceExitsSettle, finishPresenceAnimations, hasPresenceAnimationInSubtree, isPresenceAnimating, isPresenceMorphing, measurePresenceSize, preparePresenceEnter, stopPresenceAnimation, validatePresenceExitOptions };
export type { PresenceExitOptions, PresenceSize };
