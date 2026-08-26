/* SoAI - Chat feature advanced scroll preview styles [frontend/assets/ts/features/chat/chatuimanager/advancedScrollPreviewStyles.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import type { LayoutMetrics, ThumbRect } from '@features/chat/chatuimanager/advancedScrollPreviewLayout.ts';
import type { ChatUIManagerContext } from '@features/chat/chatuimanager/types.ts';

interface AdvancedScrollPreviewStyleElements {
    overlay: HTMLElement;
    viewport: HTMLElement;
    fadeTop: HTMLElement;
    fadeBottom: HTMLElement;
}

const resetAdvancedScrollPreviewStyles = (context: ChatUIManagerContext, elements: AdvancedScrollPreviewStyleElements): void => {
    context.dependencies.toggleClassName(elements.overlay, CSS_CLASSES.HOVER, false);
    context.dependencies.dom.setStyle(elements.viewport, 'top', '0px');
    context.dependencies.dom.setStyle(elements.viewport, 'height', '0px');
    context.dependencies.dom.setStyle(elements.fadeTop, 'height', '0px');
    context.dependencies.dom.setStyle(elements.fadeBottom, 'height', '0px');
};

const applyAdvancedScrollPreviewThumbStyles = (context: ChatUIManagerContext, elements: Omit<AdvancedScrollPreviewStyleElements, 'overlay'>, layout: LayoutMetrics, thumb: ThumbRect): void => {
    context.dependencies.dom.setStyle(elements.viewport, 'top', `${thumb.thumbTop}px`);
    context.dependencies.dom.setStyle(elements.viewport, 'height', `${thumb.thumbHeight}px`);
    context.dependencies.dom.setStyle(elements.fadeTop, 'height', `${Math.max(0, thumb.thumbTop)}px`);
    context.dependencies.dom.setStyle(elements.fadeBottom, 'height', `${Math.max(0, layout.grooveHeight - thumb.thumbTop - thumb.thumbHeight)}px`);
};

export { applyAdvancedScrollPreviewThumbStyles, resetAdvancedScrollPreviewStyles };
