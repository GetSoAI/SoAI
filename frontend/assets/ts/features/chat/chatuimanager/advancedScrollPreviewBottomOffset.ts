/* SoAI - Composer clearance for the chat advanced scroll preview [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewBottomOffset.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { CSS_VAR_BOTTOM_OFFSET } from '@features/chat/chatuimanager/advancedScrollPreviewConstants.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

type AdvancedScrollPreviewBottomOffsetController = {
    measure: () => number;
    apply: (valuePx: number) => void;
};

const FALLBACK_SPACING_PX = 8;
const FALLBACK_CONTROL_HEIGHT_PX = 40;

const parseCssPixelValue = (rawValue: string): number | null => {
    const trimmed = rawValue.trim();
    if (!trimmed.endsWith('px')) {
        return null;
    }
    const valuePx = Number.parseFloat(trimmed);
    return Number.isFinite(valuePx) && valuePx >= 0 ? valuePx : null;
};

const resolveRootSpacingPx = (win: Window): number => {
    const computed = win.getComputedStyle(win.document.documentElement);
    const spacingPx = parseCssPixelValue(computed.getPropertyValue('--space-2'));
    return spacingPx === null ? FALLBACK_SPACING_PX : spacingPx;
};

const resolveBoxMetricPx = (computed: CSSStyleDeclaration, propertyName: string): number => {
    const valuePx = parseCssPixelValue(computed.getPropertyValue(propertyName));
    return valuePx === null ? 0 : valuePx;
};

const resolveElementHeightPx = (win: Window, element: HTMLElement | null): number => {
    if (!element || !element.isConnected) {
        return 0;
    }
    const rect = measureLayoutBox(element);
    if (Number.isFinite(rect.height) && rect.height > 0) {
        return rect.height;
    }
    const computed = win.getComputedStyle(element);
    const heightPx = parseCssPixelValue(computed.height);
    if (heightPx !== null && heightPx > 0) {
        return heightPx;
    }
    const minHeightPx = parseCssPixelValue(computed.minHeight);
    return minHeightPx === null ? 0 : minHeightPx;
};

const resolveSingleLineInputHeightPx = (win: Window, inputWrapper: HTMLElement, fallbackPx: number): number => {
    const inputCandidate = dom.resolve('.chat-input', inputWrapper);
    if (!(inputCandidate instanceof HTMLTextAreaElement)) {
        return fallbackPx;
    }
    const computed = win.getComputedStyle(inputCandidate);
    const lineHeightPx = parseCssPixelValue(computed.lineHeight);
    const minHeightPx = parseCssPixelValue(computed.minHeight);
    if (lineHeightPx === null) {
        return minHeightPx === null ? fallbackPx : minHeightPx;
    }
    const paddingTopPx = resolveBoxMetricPx(computed, 'padding-top');
    const paddingBottomPx = resolveBoxMetricPx(computed, 'padding-bottom');
    const borderTopPx = resolveBoxMetricPx(computed, 'border-top-width');
    const borderBottomPx = resolveBoxMetricPx(computed, 'border-bottom-width');
    return Math.max(Math.ceil(lineHeightPx + paddingTopPx + paddingBottomPx + borderTopPx + borderBottomPx), minHeightPx === null ? 1 : minHeightPx);
};

const resolveBaselineWrapperHeightPx = (win: Window, inputWrapper: HTMLElement, inputActions: HTMLElement | null): number => {
    const computed = win.getComputedStyle(inputWrapper);
    const paddingTopPx = resolveBoxMetricPx(computed, 'padding-top');
    const paddingBottomPx = resolveBoxMetricPx(computed, 'padding-bottom');
    const minHeightPx = parseCssPixelValue(computed.minHeight);
    const actionHeightPx = resolveElementHeightPx(win, inputActions);
    const controlFallbackPx = actionHeightPx > 0 ? actionHeightPx : FALLBACK_CONTROL_HEIGHT_PX;
    const inputHeightPx = resolveSingleLineInputHeightPx(win, inputWrapper, controlFallbackPx);
    const contentHeightPx = inputHeightPx + actionHeightPx;
    return Math.max(minHeightPx === null ? 0 : minHeightPx, paddingTopPx + paddingBottomPx + contentHeightPx);
};

const createAdvancedScrollPreviewBottomOffsetController = (input: { context: ChatUIManagerContext; win: Window; overlay: HTMLElement; shell: HTMLElement | null; inputWrapper: HTMLElement | null; inputActions: HTMLElement | null }): AdvancedScrollPreviewBottomOffsetController => {
    let lastBottomOffsetPx: number | null = null;

    const apply = (valuePx: number): void => {
        const nextValuePx = Math.max(0, Math.round(valuePx));
        if (lastBottomOffsetPx === nextValuePx) {
            return;
        }
        lastBottomOffsetPx = nextValuePx;
        input.context.dependencies.dom.setStyle(input.overlay, CSS_VAR_BOTTOM_OFFSET, `${nextValuePx}px`);
    };

    const measure = (): number => {
        const baseSpacingPx = resolveRootSpacingPx(input.win);
        if (!input.shell || !input.shell.isConnected || !input.inputWrapper || !input.inputWrapper.isConnected) {
            return baseSpacingPx;
        }
        const shellRect = measureLayoutBox(input.shell);
        const wrapperRect = measureLayoutBox(input.inputWrapper);
        const composerClearanceHeightPx = Math.max(wrapperRect.height, resolveBaselineWrapperHeightPx(input.win, input.inputWrapper, input.inputActions));
        const composerClearanceTopPx = wrapperRect.bottom - composerClearanceHeightPx;
        const overlapPx = shellRect.bottom - composerClearanceTopPx;
        const clampedOverlapPx = clampNumber(overlapPx, 0, shellRect.height);
        return baseSpacingPx + clampedOverlapPx;
    };

    return { measure, apply };
};

export { createAdvancedScrollPreviewBottomOffsetController };
export type { AdvancedScrollPreviewBottomOffsetController };
