/* SoAI - Presence motion keyframes for appearing, disappearing and resizing controls [frontend/assets/ts/core/animations/presence/presenceMotion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measurePresenceGeometry, parsePixels, readComputedStyle, resolveAxisProperties, type PresenceGeometry } from '@core/animations/presence/presenceGeometry.ts';
import { canAnimatePresence, isPresenceAtomic } from '@core/animations/presence/presenceEligibility.ts';
import { dom } from '@core/dom/dom.ts';
import { readPresenceTokens, type PresenceTokens } from '@core/animations/presence/presenceTokens.ts';

interface PresenceFrame {
    visual: PresenceKeyframe;
    layout: PresenceKeyframe | null;
}

interface PresenceSize {
    width: number;
    height: number;
}

type PresenceKeyframe = Record<string, string | number>;

type PresencePhase = 'enter' | 'exit' | 'morph';

const runningPresenceAnimations = new Map<Element, { animation: Animation; phase: PresencePhase }>();

const canAnimate = (element: HTMLElement): boolean => typeof element.animate === 'function';

const trackPresenceAnimation = (element: HTMLElement, animation: Animation, phase: PresencePhase): Animation => {
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

const isPresenceMorphing = (element: Element): boolean => runningPresenceAnimations.get(element)?.phase === 'morph';

const finishPresenceAnimations = (root: Document | Element): void => {
    for (const [element, record] of runningPresenceAnimations) {
        if (root.contains(element)) {
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
const interruptPresenceAnimation = (element: HTMLElement): PresenceFrame | null => {
    const animation = runningPresenceAnimations.get(element)?.animation;
    const style = animation ? readComputedStyle(element) : null;
    if (!animation || !style) {
        animation?.cancel();
        return null;
    }
    const frame = {
        visual: { opacity: style.opacity, scale: style.scale, filter: style.filter },
        layout: captureLayoutFrame(style, measurePresenceGeometry(element))
    };
    stopPresenceAnimation(element);
    return frame;
};
const buildHiddenVisualKeyframe = (tokens: PresenceTokens): PresenceKeyframe => ({
    opacity: 0,
    scale: tokens.scaleFrom,
    filter: `blur(${tokens.blurFrom})`
});

const CONTROL_SELECTOR = "button, [role='button']";
const VISUAL_ONLY_ATTRIBUTE = 'data-presence-visual-only';

const resolveVisualTargets = (element: HTMLElement): HTMLElement[] => {
    if (element.matches(CONTROL_SELECTOR) || isPresenceAtomic(element)) {
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
    const frame = interruptPresenceAnimation(element);
    const useVisualOnly = visualOnly || element.hasAttribute(VISUAL_ONLY_ATTRIBUTE);
    const layout = buildLayoutKeyframes(element, useVisualOnly ? null : measurePresenceGeometry(element), useVisualOnly);
    const from = { ...layout.collapsed, ...frame?.layout, ...(ownsVisual ? (frame?.visual ?? buildHiddenVisualKeyframe(tokens)) : {}) };
    return () => {
        children.forEach((start) => start());
        if (tokens.enterDurationMs <= 0 || !canAnimate(element)) {
            return null;
        }
        const animation = element.animate([from, layout.expanded], { duration: tokens.enterDurationMs, easing: tokens.enterEasing });
        return trackPresenceAnimation(element, animation, 'enter');
    };
};

const animatePresenceExit = (element: HTMLElement, visualOnly = false): Animation | null => {
    const tokens = readPresenceTokens(element);
    const frame = interruptPresenceAnimation(element);
    if (tokens.exitDurationMs <= 0 || !canAnimate(element) || !canAnimatePresence(element)) {
        return null;
    }
    const targets = resolveVisualTargets(element);
    const ownsVisual = targets.includes(element);
    const useVisualOnly = visualOnly || element.hasAttribute(VISUAL_ONLY_ATTRIBUTE);
    const layout = buildLayoutKeyframes(element, useVisualOnly ? null : measurePresenceGeometry(element), useVisualOnly);
    const from = { ...layout.expanded, ...frame?.layout, ...(ownsVisual ? frame?.visual : {}) };
    const to = { ...layout.collapsed, ...(ownsVisual ? buildHiddenVisualKeyframe(tokens) : {}) };
    const animation = element.animate([from, to], { duration: tokens.exitDurationMs, easing: tokens.exitEasing, fill: 'forwards' });
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
const CLIP_KEYFRAME: PresenceKeyframe = { overflow: 'clip', whiteSpace: 'nowrap' };

const animatePresenceMorph = (element: HTMLElement, from: PresenceSize, to: PresenceSize): Animation | null => {
    const tokens = readPresenceTokens(element);
    const widthChanged = Math.abs(from.width - to.width) > MORPH_THRESHOLD_PX;
    const heightChanged = Math.abs(from.height - to.height) > MORPH_THRESHOLD_PX;
    if ((!widthChanged && !heightChanged) || tokens.morphDurationMs <= 0 || !canAnimate(element) || !canAnimatePresence(element, { allowAtomicMorph: true }) || isPresenceAnimating(element)) {
        return null;
    }
    const start: PresenceKeyframe = { ...CLIP_KEYFRAME, minWidth: '0px', minHeight: '0px' };
    const end: PresenceKeyframe = { ...CLIP_KEYFRAME, minWidth: '0px', minHeight: '0px' };
    if (widthChanged) {
        start['width'] = `${from.width}px`;
        end['width'] = `${to.width}px`;
    }
    if (heightChanged) {
        start['height'] = `${from.height}px`;
        end['height'] = `${to.height}px`;
    }
    const options = { duration: tokens.morphDurationMs, easing: tokens.enterEasing };
    Array.from(element.children).forEach((child) => {
        if (child instanceof HTMLElement && canAnimate(child) && canAnimatePresence(child)) {
            const opacity = isPresenceMorphing(child) ? readComputedStyle(child)?.opacity : tokens.morphFadeFrom;
            stopPresenceAnimation(child);
            trackPresenceAnimation(child, child.animate([{ opacity: opacity ?? tokens.morphFadeFrom }, {}], options), 'morph');
        }
    });
    return trackPresenceAnimation(element, element.animate([start, end], options), 'morph');
};

export { animatePresenceExit, animatePresenceMorph, finishPresenceAnimations, isPresenceAnimating, isPresenceMorphing, measurePresenceSize, preparePresenceEnter, stopPresenceAnimation };
export type { PresenceSize };
