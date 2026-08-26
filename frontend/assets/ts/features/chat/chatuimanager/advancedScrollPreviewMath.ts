/* SoAI - Advanced scroll preview geometry calculations [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewMath.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';

export type AdvancedScrollPreviewFitInput = {
    isWidescreen: boolean;
    isNarrowViewport: boolean;
    isScrollable: boolean;
    scrollOverflowPx: number;
    minScrollOverflowPx: number;
};

export const canShowAdvancedScrollPreview = (input: AdvancedScrollPreviewFitInput): boolean => {
    if (input.isWidescreen || input.isNarrowViewport || !input.isScrollable) {
        return false;
    }
    if (input.scrollOverflowPx < input.minScrollOverflowPx) {
        return false;
    }
    return true;
};

export type AdvancedScrollPreviewThumbInput = {
    grooveHeight: number;
    scrollHeight: number;
    clientHeight: number;
    scrollTop: number;
    minThumbHeightPx: number;
};

export type AdvancedScrollPreviewThumbRect = {
    thumbTop: number;
    thumbHeight: number;
};

export const computeAdvancedScrollPreviewThumb = (input: AdvancedScrollPreviewThumbInput): AdvancedScrollPreviewThumbRect => {
    const grooveHeight = Math.max(0, input.grooveHeight);
    const scrollHeight = Math.max(0, input.scrollHeight);
    const clientHeight = Math.max(0, input.clientHeight);
    const maxScrollTop = Math.max(0, scrollHeight - clientHeight);
    const thumbHeightRaw = scrollHeight > 0 ? (clientHeight / scrollHeight) * grooveHeight : grooveHeight;
    const thumbHeight = clampNumber(Math.round(Math.max(input.minThumbHeightPx, thumbHeightRaw)), 0, grooveHeight);
    const denom = Math.max(1, grooveHeight - thumbHeight);
    const thumbTopRaw = maxScrollTop > 0 ? (clampNumber(input.scrollTop, 0, maxScrollTop) / maxScrollTop) * denom : 0;
    return {
        thumbTop: clampNumber(thumbTopRaw, 0, Math.max(0, grooveHeight - thumbHeight)),
        thumbHeight
    };
};

export type AdvancedScrollPreviewClickInput = {
    clickY: number;
    grooveHeight: number;
    scrollHeight: number;
    clientHeight: number;
};

export const mapAdvancedScrollPreviewClickToScrollTop = (input: AdvancedScrollPreviewClickInput): number => {
    const grooveHeight = Math.max(1, input.grooveHeight);
    const scrollHeight = Math.max(0, input.scrollHeight);
    const clientHeight = Math.max(0, input.clientHeight);
    const maxScrollTop = Math.max(0, scrollHeight - clientHeight);
    const clickY = clampNumber(input.clickY, 0, grooveHeight);
    const target = (clickY / grooveHeight) * scrollHeight - clientHeight / 2;
    return clampNumber(target, 0, maxScrollTop);
};
