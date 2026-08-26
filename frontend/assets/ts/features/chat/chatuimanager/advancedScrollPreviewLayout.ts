/* SoAI - Advanced scroll preview visibility and geometry [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewLayout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { canShowAdvancedScrollPreview, computeAdvancedScrollPreviewThumb } from '@features/chat/chatuimanager/advancedScrollPreviewMath.ts';
import { MIN_SCROLL_OVERFLOW_TO_SHOW_PX, MIN_SCROLL_OVERFLOW_VIEWPORT_RATIO, MIN_THUMB_HEIGHT_PX, VIEWPORT_EDGE_INSET_PX } from '@features/chat/chatuimanager/advancedScrollPreviewConstants.ts';

type LayoutMetrics = {
    visibleWanted: boolean;
    grooveHeight: number;
    scrollHeight: number;
    clientHeight: number;
    maxScrollTop: number;
};

type ThumbRect = {
    thumbTop: number;
    thumbHeight: number;
};

const computeAdvancedScrollPreviewLayoutMetrics = (inputArguments: { grooveHeight: number; scrollHeight: number; clientHeight: number; isWidescreen: boolean; isNarrowViewport: boolean; hasEverBeenScrollable: boolean }): LayoutMetrics => {
    const grooveHeight = Math.max(0, inputArguments.grooveHeight);
    const scrollHeight = Math.max(0, inputArguments.scrollHeight);
    const clientHeight = Math.max(0, inputArguments.clientHeight);
    const maxScrollTop = Math.max(0, scrollHeight - clientHeight);
    const scrollOverflowPx = Math.max(0, scrollHeight - clientHeight);
    const minScrollOverflowPx = Math.max(MIN_SCROLL_OVERFLOW_TO_SHOW_PX, Math.round(clientHeight * MIN_SCROLL_OVERFLOW_VIEWPORT_RATIO));

    return {
        visibleWanted: canShowAdvancedScrollPreview({
            isWidescreen: inputArguments.isWidescreen,
            isNarrowViewport: inputArguments.isNarrowViewport,
            isScrollable: inputArguments.hasEverBeenScrollable,
            scrollOverflowPx,
            minScrollOverflowPx
        }),
        grooveHeight,
        scrollHeight,
        clientHeight,
        maxScrollTop
    };
};

const computeAdvancedScrollPreviewThumbRect = (layout: LayoutMetrics, scrollTop: number): ThumbRect => {
    const thumb = computeAdvancedScrollPreviewThumb({
        grooveHeight: layout.grooveHeight,
        scrollHeight: layout.scrollHeight,
        clientHeight: layout.clientHeight,
        scrollTop,
        minThumbHeightPx: MIN_THUMB_HEIGHT_PX
    });

    const maxViewportHeightPx = Math.max(0, layout.grooveHeight - VIEWPORT_EDGE_INSET_PX * 2);
    const snappedThumbHeightPx = clampNumber(Math.round(thumb.thumbHeight), 0, maxViewportHeightPx);
    const maxViewportTopPx = Math.max(0, layout.grooveHeight - VIEWPORT_EDGE_INSET_PX - snappedThumbHeightPx);
    const minViewportTopPx = Math.min(VIEWPORT_EDGE_INSET_PX, maxViewportTopPx);
    const snappedThumbTopPx = clampNumber(Math.floor(thumb.thumbTop), minViewportTopPx, maxViewportTopPx);
    return { thumbTop: snappedThumbTopPx, thumbHeight: snappedThumbHeightPx };
};

export { computeAdvancedScrollPreviewLayoutMetrics, computeAdvancedScrollPreviewThumbRect };
export type { LayoutMetrics, ThumbRect };
