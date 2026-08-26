/* SoAI - Parses CSS transition/animation duration strings and returns the max duration in milliseconds [frontend/assets/ts/core/animations/parseMaxCssDurationMs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const parseMaxCssDurationMs = (raw: string): number => {
    const normalized = raw.trim();
    if (!normalized) {
        return 0;
    }
    let maxMs = 0;
    for (const part of normalized.split(',')) {
        const token = part.trim();
        if (!token) {
            continue;
        }
        const msMatch = /^(\d+(?:\.\d+)?)ms$/.exec(token);
        if (msMatch) {
            const matchValue = msMatch[1];
            if (!matchValue) {
                continue;
            }
            const value = Number.parseFloat(matchValue);
            if (Number.isFinite(value)) {
                maxMs = Math.max(maxMs, Math.round(value));
            }
            continue;
        }
        const secMatch = /^(\d+(?:\.\d+)?)s$/.exec(token);
        if (secMatch) {
            const matchValue = secMatch[1];
            if (!matchValue) {
                continue;
            }
            const value = Number.parseFloat(matchValue);
            if (Number.isFinite(value)) {
                maxMs = Math.max(maxMs, Math.round(value * 1000));
            }
        }
    }
    return Math.max(0, maxMs);
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
