/* SoAI - Shared frontend page actions menu position [frontend/assets/ts/core/pageActionsMenuPosition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

const MENU_VIEWPORT_GAP_PX = 8;

const clearPageActionsMenuPosition = (menu: HTMLElement): void => {
    dom.setStyle(menu, '--page-actions-menu-left', null);
    dom.setStyle(menu, '--page-actions-menu-top', null);
    dom.setStyle(menu, '--page-actions-menu-max-width', null);
};

const syncPageActionsMenuPosition = (menu: HTMLElement, trigger: HTMLElement): void => {
    const { width: viewportWidth, height: viewportHeight } = measureLayoutViewport(menu);
    const maxWidth = Math.max(0, viewportWidth - MENU_VIEWPORT_GAP_PX * 2);
    dom.setStyle(menu, '--page-actions-menu-max-width', `${String(maxWidth)}px`);
    const triggerRect = measureLayoutBox(trigger);
    const menuRect = measureLayoutBox(menu);
    const menuWidth = Math.min(menuRect.width, maxWidth);
    const menuHeight = menuRect.height;
    const preferredLeft = triggerRect.right - menuWidth;
    const maxLeft = Math.max(MENU_VIEWPORT_GAP_PX, viewportWidth - menuWidth - MENU_VIEWPORT_GAP_PX);
    const left = Math.min(Math.max(MENU_VIEWPORT_GAP_PX, preferredLeft), maxLeft);
    const belowTop = triggerRect.bottom + MENU_VIEWPORT_GAP_PX;
    const aboveTop = triggerRect.top - menuHeight - MENU_VIEWPORT_GAP_PX;
    const shouldOpenAbove = belowTop + menuHeight > viewportHeight - MENU_VIEWPORT_GAP_PX && aboveTop >= MENU_VIEWPORT_GAP_PX;
    const preferredTop = shouldOpenAbove ? aboveTop : belowTop;
    const maxTop = Math.max(MENU_VIEWPORT_GAP_PX, viewportHeight - menuHeight - MENU_VIEWPORT_GAP_PX);
    const top = Math.min(Math.max(MENU_VIEWPORT_GAP_PX, preferredTop), maxTop);
    const containingBlockRect = isHTMLElement(menu.offsetParent) ? measureLayoutBox(menu.offsetParent) : null;
    const adjustedLeft = containingBlockRect ? left - containingBlockRect.left : left;
    const adjustedTop = containingBlockRect ? top - containingBlockRect.top : top;
    dom.setStyle(menu, '--page-actions-menu-left', `${String(adjustedLeft)}px`);
    dom.setStyle(menu, '--page-actions-menu-top', `${String(adjustedTop)}px`);
};

export { clearPageActionsMenuPosition, syncPageActionsMenuPosition };
