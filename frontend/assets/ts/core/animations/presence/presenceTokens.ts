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
    morphFadeFrom: number;
}

const FALLBACK_EASING = 'ease';

const readTokenText = (style: CSSStyleDeclaration, name: string): string => style.getPropertyValue(name).trim();

const readTokenNumber = (style: CSSStyleDeclaration, name: string, fallback: number): number => {
    const value = Number.parseFloat(readTokenText(style, name));
    return Number.isFinite(value) ? value : fallback;
};

const readTokenDurationMs = (style: CSSStyleDeclaration, name: string, reduced: boolean): number => (reduced ? 0 : parseMaxCssDurationMs(readTokenText(style, name)));
const readPresenceTokens = (element: Element): PresenceTokens => {
    const documentRef = element.ownerDocument;
    const view = documentRef.defaultView;
    const style = view ? view.getComputedStyle(documentRef.documentElement) : null;
    const reduced = isReducedAnimationScope(documentRef);
    if (!style) {
        return { enterDurationMs: 0, exitDurationMs: 0, morphDurationMs: 0, enterEasing: FALLBACK_EASING, exitEasing: FALLBACK_EASING, scaleFrom: 1, blurFrom: '0px', morphFadeFrom: 1 };
    }
    return {
        enterDurationMs: readTokenDurationMs(style, '--presence-enter-duration', reduced),
        exitDurationMs: readTokenDurationMs(style, '--presence-exit-duration', reduced),
        morphDurationMs: readTokenDurationMs(style, '--presence-morph-duration', reduced),
        enterEasing: readTokenText(style, '--presence-enter-ease') || FALLBACK_EASING,
        exitEasing: readTokenText(style, '--presence-exit-ease') || FALLBACK_EASING,
        scaleFrom: readTokenNumber(style, '--presence-scale-from', 1),
        blurFrom: readTokenText(style, '--presence-blur-from') || '0px',
        morphFadeFrom: readTokenNumber(style, '--presence-morph-fade-from', 1)
    };
};

export { readPresenceTokens };
export type { PresenceTokens };
