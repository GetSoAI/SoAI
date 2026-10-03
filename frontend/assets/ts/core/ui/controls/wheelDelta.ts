/* SoAI - Shared frontend wheel delta normalization to pixels [frontend/assets/ts/core/ui/controls/wheelDelta.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const LINE_WHEEL_DELTA_PX = 16;

const normalizeWheelDeltaPx = (value: number, deltaMode: number, pageSizePx: number): number => {
    if (deltaMode === WheelEvent.DOM_DELTA_LINE) {
        return value * LINE_WHEEL_DELTA_PX;
    }
    if (deltaMode === WheelEvent.DOM_DELTA_PAGE) {
        return value * Math.max(pageSizePx, 1);
    }
    return value;
};

export { normalizeWheelDeltaPx };
