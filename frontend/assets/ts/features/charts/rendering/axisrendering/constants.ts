/* SoAI - Charts feature axis rendering constants [frontend/assets/ts/features/charts/rendering/axisrendering/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const { max, min } = Math;

const { isFinite: isFin } = Number;

const LOG_SAFE_MIN = 1e-9;
const DEFAULT_Y_TICK_COUNT = 6;
const MIN_LABEL_GAP = 6;
const AXIS_FONT_SIZE = 12;
const X_AXIS_PADDING = 8;
const X_AXIS_GAP_RATIO = 0.45;

const MIN_VERTICAL_CONTENT_INSET = 6;
const MAX_VERTICAL_CONTENT_INSET_RATIO = 0.1;

const X_AXIS_BREAKPOINTS: readonly { width: number; labels: number }[] = Object.freeze([
    { width: 320, labels: 2 },
    { width: 420, labels: 3 },
    { width: 520, labels: 4 },
    { width: 640, labels: 5 },
    { width: 760, labels: 6 },
    { width: 880, labels: 7 }
]);

const resolveVerticalContentInset = (height: number): number => {
    if (!isFin(height) || height <= 0) {
        return MIN_VERTICAL_CONTENT_INSET;
    }
    return min(height / 2, max(MIN_VERTICAL_CONTENT_INSET, height * MAX_VERTICAL_CONTENT_INSET_RATIO));
};

const determineXAxisLabelBudget = (width: number): number => {
    const normalizedWidth = max(0, Number(width) || 0);
    for (const breakpoint of X_AXIS_BREAKPOINTS) {
        if (normalizedWidth <= breakpoint.width) {
            return breakpoint.labels;
        }
    }
    return 8;
};

const getXAxisFont = (): string => '12px sans-serif';

export { LOG_SAFE_MIN, DEFAULT_Y_TICK_COUNT, MIN_LABEL_GAP, AXIS_FONT_SIZE, X_AXIS_PADDING, X_AXIS_GAP_RATIO, resolveVerticalContentInset, determineXAxisLabelBudget, getXAxisFont };
