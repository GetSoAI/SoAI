/* SoAI - Parses CSS transition/animation duration strings and returns the max duration in milliseconds [frontend/assets/ts/core/animations/parseMaxCssDurationMs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const CSS_TIME_PATTERN = /^(\d*\.?\d+)(ms|s)$/u;

const parseMaxCssDurationMs = (raw: string): number => {
    let maxMs = 0;
    for (const part of raw.split(',')) {
        const match = CSS_TIME_PATTERN.exec(part.trim());
        if (!match?.[1]) {
            continue;
        }
        const ms = Number.parseFloat(match[1]) * (match[2] === 's' ? 1000 : 1);
        if (Number.isFinite(ms)) {
            maxMs = Math.max(maxMs, Math.round(ms));
        }
    }
    return maxMs;
};

const resolveMaxCssTransitionDurationMs = (element: HTMLElement): number => {
    const view = element.ownerDocument.defaultView;
    if (!view) {
        return 0;
    }
    const style = view.getComputedStyle(element);
    return parseMaxCssDurationMs(style.transitionDuration);
};

const resolveMaxCssTransitionTotalMs = (element: HTMLElement): number => {
    const view = element.ownerDocument.defaultView;
    if (!view) {
        return 0;
    }
    const style = view.getComputedStyle(element);
    const durationMs = parseMaxCssDurationMs(style.transitionDuration);
    const delayMs = parseMaxCssDurationMs(style.transitionDelay);
    return Math.max(0, durationMs + delayMs);
};

const resolveMaxCssAnimationTotalMs = (element: HTMLElement): number => {
    const view = element.ownerDocument.defaultView;
    if (!view) {
        return 0;
    }
    const style = view.getComputedStyle(element);
    const durationMs = parseMaxCssDurationMs(style.animationDuration);
    const delayMs = parseMaxCssDurationMs(style.animationDelay);
    return Math.max(0, durationMs + delayMs);
};

export { parseMaxCssDurationMs, resolveMaxCssAnimationTotalMs, resolveMaxCssTransitionDurationMs, resolveMaxCssTransitionTotalMs };
