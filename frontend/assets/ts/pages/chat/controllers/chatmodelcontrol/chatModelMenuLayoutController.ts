/* SoAI - Chat model popover geometry and presentation lifetime [frontend/assets/ts/pages/chat/controllers/chatmodelcontrol/chatModelMenuLayoutController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getWindow } from '@core/environment/public.ts';
import { measureLayoutBox, measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { MENU_VIEWPORT_GAP_PX, syncPageActionsMenuPosition } from '@core/pageActionsMenuPosition.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { scrollElementToScrollerCenter } from '@core/scroll.ts';
import type { ModelControlScope } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlWidget.ts';

const CHAT_MODEL_MENU_CURRENT_OPTION_SELECTOR = ".chat-model-menu-option[aria-current='true']:not(.u-hidden)";

const openChatModelMenuLayout = (menu: HTMLElement, trigger: HTMLElement, scope: ModelControlScope, boundary: HTMLElement | null): (() => void) => {
    const controller = new AbortController();
    const sync = (): void => {
        const triggerRect = measureLayoutBox(trigger);
        const availableHeight = scope === 'composer' && boundary !== null ? triggerRect.top - MENU_VIEWPORT_GAP_PX - measureLayoutBox(boundary).bottom : (boundary === null ? measureLayoutViewport(menu).height - MENU_VIEWPORT_GAP_PX : measureLayoutBox(boundary).bottom) - triggerRect.bottom - MENU_VIEWPORT_GAP_PX;
        dom.setStyle(menu, '--chat-model-menu-max-height', `${String(Math.max(0, availableHeight))}px`);
        dom.flush();
        syncPageActionsMenuPosition(menu, trigger, scope === 'composer' ? { alignment: 'start', placement: 'above' } : { alignment: 'start' });
        dom.flush();
    };
    const observer = new ResizeObserver(sync);
    const layoutRoot = scope === 'composer' ? trigger.closest('.chat-input-actions') : trigger.parentElement;
    if (layoutRoot === null) throw new Error('Chat model menu requires its control layout surface');
    const layoutObserver = new MutationObserver((records) => {
        if (records.some((record) => !menu.contains(record.target))) sync();
    });
    const releaseResources = (): void => {
        observer.disconnect();
        layoutObserver.disconnect();
        controller.abort();
    };
    let opened = false;
    menu.addEventListener(
        'beforetoggle',
        (event: Event): void => {
            if (event instanceof ToggleEvent && event.newState === 'closed') {
                releaseResources();
            }
        },
        { signal: controller.signal }
    );
    try {
        menu.showPopover();
        opened = true;
        sync();
        const currentOption = dom.resolve(CHAT_MODEL_MENU_CURRENT_OPTION_SELECTOR, menu);
        if (currentOption instanceof HTMLElement) {
            scrollElementToScrollerCenter(menu, currentOption, { behavior: 'instant' });
        }
        observer.observe(trigger);
        observer.observe(menu);
        observer.observe(layoutRoot);
        layoutObserver.observe(layoutRoot, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'data-presence-state'] });
        if (boundary !== null) observer.observe(boundary);
        const windowRef = getWindow();
        windowRef.addEventListener('resize', sync, { signal: controller.signal });
        windowRef.addEventListener(INTERFACE_SCALE_CHANGED_EVENT, sync, { signal: controller.signal });
        menu.ownerDocument.addEventListener('scroll', sync, { capture: true, signal: controller.signal });
    } catch (error) {
        releaseResources();
        if (opened) menu.hidePopover();
        throw ensureError(error);
    }
    return (): void => {
        releaseResources();
        if (menu.isConnected) menu.hidePopover();
    };
};

export { openChatModelMenuLayout };
