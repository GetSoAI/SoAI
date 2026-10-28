/* SoAI - Presence motion design tokens [frontend/assets/ts/core/animations/presence/presenceTokens.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { isReducedAnimationScope } from '@core/animations/speed.ts';

interface PresenceTokens {
    enterDurationMs: number;
    exitDurationMs: number;
    morphDurationMs: number;
    enterEasing: string;
    exitEasing: string;
    scaleFrom: number;
    blurFrom: string;
    translateFrom: string;
    morphFadeFrom: number;
}

const FALLBACK_EASING = 'ease';

const readTokenText = (style: CSSStyleDeclaration, name: string, inheritedStyle: CSSStyleDeclaration): string => style.getPropertyValue(name).trim() || inheritedStyle.getPropertyValue(name).trim();

const readTokenNumber = (style: CSSStyleDeclaration, name: string, fallback: number, inheritedStyle: CSSStyleDeclaration): number => {
    const value = Number.parseFloat(readTokenText(style, name, inheritedStyle));
    return Number.isFinite(value) ? value : fallback;
};

const readTokenDurationMs = (style: CSSStyleDeclaration, name: string, reduced: boolean, inheritedStyle: CSSStyleDeclaration): number => (reduced ? 0 : parseMaxCssDurationMs(readTokenText(style, name, inheritedStyle)));
const readPresenceTokens = (element: Element): PresenceTokens => {
    const documentRef = element.ownerDocument;
    const view = documentRef.defaultView;
    const inheritedStyle = view ? view.getComputedStyle(documentRef.documentElement) : null;
    const style = view ? view.getComputedStyle(element) : null;
    const reduced = isReducedAnimationScope(documentRef);
    if (!style || !inheritedStyle) {
        return { enterDurationMs: 0, exitDurationMs: 0, morphDurationMs: 0, enterEasing: FALLBACK_EASING, exitEasing: FALLBACK_EASING, scaleFrom: 1, blurFrom: '0px', translateFrom: '', morphFadeFrom: 1 };
    }
    return {
        enterDurationMs: readTokenDurationMs(style, '--presence-enter-duration', reduced, inheritedStyle),
        exitDurationMs: readTokenDurationMs(style, '--presence-exit-duration', reduced, inheritedStyle),
        morphDurationMs: readTokenDurationMs(style, '--presence-morph-duration', reduced, inheritedStyle),
        enterEasing: readTokenText(style, '--presence-enter-ease', inheritedStyle) || FALLBACK_EASING,
        exitEasing: readTokenText(style, '--presence-exit-ease', inheritedStyle) || FALLBACK_EASING,
        scaleFrom: readTokenNumber(style, '--presence-scale-from', 1, inheritedStyle),
        blurFrom: readTokenText(style, '--presence-blur-from', inheritedStyle) || '0px',
        translateFrom: readTokenText(style, '--presence-translate-from', inheritedStyle),
        morphFadeFrom: readTokenNumber(style, '--presence-morph-fade-from', 1, inheritedStyle)
    };
};

export { readPresenceTokens };
export type { PresenceTokens };
