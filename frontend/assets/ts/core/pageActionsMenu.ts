/* SoAI - Shared frontend page actions menu [frontend/assets/ts/core/pageActionsMenu.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getComputedStyleStrict, getDocument, getWindow } from '@core/environment/public.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { clearPageActionsMenuPosition, syncPageActionsMenuPosition } from '@core/pageActionsMenuPosition.ts';
import { isHTMLElement, isInstanceOf, isNumber } from '@core/typeGuards.ts';

const DEFAULT_BREAKPOINT = 1024;
const EXTENDED_BREAKPOINT = 1400;
const FIT_RECOVERY_ROOM_PX = 24;
const CLASS_OPEN = 'page-actions__menu--open';
const CLASS_DROPDOWN = 'page-actions--dropdown';

interface PageActionsMenuHost {
    on: (target: EventTarget, event: string, handler: EventListener) => (() => void) | void;
}

interface PageActionsMenuOptions {
    host: PageActionsMenuHost;
    breakpoint?: number;
    sidebarStateProvider?: () => boolean;
    selectors?: Partial<{
        wrapper: string;
        trigger: string;
        menu: string;
    }>;
    alwaysDropdown?: boolean;
    collapseToFit?: boolean;
    onCollapsedChange?: (collapsed: boolean) => void;
}

export class PageActionsMenuManager {
    #host: PageActionsMenuHost;
    #wrapper: HTMLElement | null;
    #trigger: HTMLElement | null;
    #menu: HTMLElement | null;
    #isOpen: boolean;
    #viewportResizeCleanup: (() => void) | null;
    #viewportScaleCleanup: (() => void) | null;
    #breakpoint: number;
    #sidebarStateProvider: (() => boolean) | null;
    #selectors: { wrapper: string; trigger: string; menu: string };
    #alwaysDropdown: boolean;
    #collapseToFit: boolean;
    #positionAbortController: AbortController | null;
    #positionScaleCleanup: (() => void) | null;
    #onCollapsedChange: ((collapsed: boolean) => void) | null;
    #collapsed: boolean | null;

    constructor({ host, breakpoint, sidebarStateProvider, selectors, alwaysDropdown, collapseToFit, onCollapsedChange }: PageActionsMenuOptions) {
        this.#host = host;
        this.#breakpoint = isNumber(breakpoint) && breakpoint > 0 ? breakpoint : DEFAULT_BREAKPOINT;
        this.#sidebarStateProvider = sidebarStateProvider || null;
        this.#wrapper = null;
        this.#trigger = null;
        this.#menu = null;
        this.#isOpen = false;
        this.#viewportResizeCleanup = null;
        this.#viewportScaleCleanup = null;
        this.#selectors = {
            wrapper: selectors?.wrapper ?? '.page-actions',
            trigger: selectors?.trigger ?? '.page-actions__trigger',
            menu: selectors?.menu ?? '.page-actions__menu'
        };
        this.#alwaysDropdown = alwaysDropdown === true;
        this.#collapseToFit = collapseToFit === true;
        this.#positionAbortController = null;
        this.#positionScaleCleanup = null;
        this.#onCollapsedChange = onCollapsedChange ?? null;
        this.#collapsed = null;
    }

    initialize(container: HTMLElement | null): boolean {
        if (!isHTMLElement(container)) return false;

        const wrapper = dom.resolve(this.#selectors.wrapper, container);
        if (!isHTMLElement(wrapper)) return false;

        const trigger = dom.resolve(this.#selectors.trigger, wrapper);
        const menu = dom.resolve(this.#selectors.menu, wrapper);
        if (!(isHTMLElement(trigger) && isHTMLElement(menu))) return false;

        this.#wrapper = wrapper;
        this.#trigger = trigger;
        this.#menu = menu;
        const resolvedMenu = menu;
        const documentTarget = getDocument();

        this.#host.on(wrapper, 'click', (error: Event) => {
            const target = error.target;
            if (!isInstanceOf(target, Element)) return;
            const currentTrigger = target.closest(this.#selectors.trigger);
            if (isHTMLElement(currentTrigger) && wrapper.contains(currentTrigger)) {
                this.#trigger = currentTrigger;
                error.preventDefault();
                error.stopPropagation();
                this.toggle();
                return;
            }
            if (!this.#isOpen) return;
            if (target.matches('input, textarea, select, [contenteditable]')) return;
            if (target.closest('input, textarea, select, [contenteditable]')) return;
            if (target.closest('.searchbar-container, [class*="search"]')) return;
            const clickable = target.matches('button, .ui-button, .ui-icon-button, [role="button"]') ? target : target.closest('button, .ui-button, .ui-icon-button, [role="button"]');
            if (!(isHTMLElement(clickable) && resolvedMenu.contains(clickable))) return;
            if (clickable.getAttribute('aria-disabled') === 'true' || clickable.getAttribute('data-toggle-disabled') === 'true') return;
            if (clickable instanceof HTMLButtonElement && clickable.disabled) return;
            if (clickable.closest('[data-page-actions-menu-keep-open="true"]')) return;
            this.hide();
        });

        this.#host.on(documentTarget, 'click', (error: Event) => {
            const target = error.target;
            const wrapperRef = this.#wrapper;
            if (this.#isOpen && wrapperRef && isInstanceOf(target, Node) && !wrapperRef.contains(target)) {
                this.hide();
            }
        });

        this.#host.on(documentTarget, 'keydown', (error: Event) => {
            if (!(error instanceof KeyboardEvent)) {
                return;
            }
            if (error.key === 'Escape' && this.#isOpen) {
                error.stopPropagation();
                this.hide();
                const triggerRef = this.#trigger;
                if (triggerRef) {
                    triggerRef.focus();
                }
            }
        });

        if (this.#alwaysDropdown) {
            this.#commitDropdownState(true);
        } else {
            this.#commitDropdownState(this.#shouldShowDropdown());
            const windowRef = wrapper.ownerDocument.defaultView;
            if (!windowRef) {
                throw new Error('Page actions menu requires a document window');
            }
            const resizeCleanup = this.#host.on(windowRef, 'resize', () => this.updateDropdownState());
            this.#viewportResizeCleanup = typeof resizeCleanup === 'function' ? resizeCleanup : null;
            const scaleCleanup = this.#host.on(windowRef, INTERFACE_SCALE_CHANGED_EVENT, () => this.updateDropdownState());
            this.#viewportScaleCleanup = typeof scaleCleanup === 'function' ? scaleCleanup : null;
        }

        this.#host.on(resolvedMenu, 'change', (error: Event) => {
            const target = error.target;
            if (!isInstanceOf(target, Element)) return;
            const closesMenu = target.matches('input[type="checkbox"], [data-page-actions-menu-close-on-change="true"]');
            if (closesMenu && this.#isOpen) {
                this.hide();
            }
        });

        return true;
    }

    #shouldShowDropdown(): boolean {
        const wrapper = this.#wrapper;
        if (!wrapper) return false;
        const width = measureLayoutViewport(wrapper).width;
        if (width <= this.#breakpoint) return true;
        if (width <= EXTENDED_BREAKPOINT && this.#sidebarStateProvider) {
            return this.#sidebarStateProvider();
        }
        return this.#collapseToFit && this.#expandedMenuDoesNotFit();
    }

    #expandedMenuDoesNotFit(): boolean {
        const wrapper = this.#wrapper;
        const menu = this.#menu;
        const pageHeader = wrapper?.closest('.page-header');
        const titleSection = pageHeader ? dom.resolve('.page-header-title-section', pageHeader) : null;
        if (!(wrapper && menu && pageHeader instanceof HTMLElement && titleSection instanceof HTMLElement)) {
            return false;
        }
        const wasCollapsed = wrapper.classList.contains(CLASS_DROPDOWN);
        if (wasCollapsed) {
            dom.removeClass(wrapper, CLASS_DROPDOWN);
        }
        try {
            const headerStyle = getComputedStyleStrict(pageHeader);
            const gap = parseFloat(headerStyle.columnGap || headerStyle.gap) || 0;
            const recoveryRoom = wasCollapsed ? FIT_RECOVERY_ROOM_PX : 0;
            const requiredWidth = Math.ceil(titleSection.scrollWidth + menu.scrollWidth + gap + recoveryRoom);
            const availableWidth = Math.floor(pageHeader.clientWidth);
            return requiredWidth > availableWidth;
        } finally {
            if (wasCollapsed) {
                dom.addClass(wrapper, CLASS_DROPDOWN);
            }
        }
    }

    updateDropdownState(): void {
        if (!this.#wrapper || this.#alwaysDropdown) return;
        this.#commitDropdownState(this.#shouldShowDropdown());
    }

    #commitDropdownState(shouldShowDropdown: boolean): void {
        const wrapper = this.#wrapper;
        if (!wrapper) return;
        if (shouldShowDropdown) {
            dom.addClass(wrapper, CLASS_DROPDOWN);
        } else {
            dom.removeClass(wrapper, CLASS_DROPDOWN);
            if (this.#isOpen) this.hide();
        }
        if (this.#collapsed === shouldShowDropdown) return;
        this.#collapsed = shouldShowDropdown;
        this.#onCollapsedChange?.(shouldShowDropdown);
    }

    show(): void {
        if (!this.#menu || !this.#trigger) return;
        dom.addClass(this.#menu, CLASS_OPEN);
        dom.setAttribute(this.#trigger, 'aria-expanded', 'true');
        this.#isOpen = true;
        this.#syncMenuPosition();
        this.#bindPositionUpdates();
    }

    hide(): void {
        if (!this.#menu || !this.#trigger) return;
        dom.removeClass(this.#menu, CLASS_OPEN);
        dom.setAttribute(this.#trigger, 'aria-expanded', 'false');
        this.#clearMenuPosition();
        this.#unbindPositionUpdates();
        this.#isOpen = false;
    }

    toggle(): void {
        if (this.#isOpen) {
            this.hide();
        } else {
            this.show();
        }
    }

    dispose(): void {
        this.#onCollapsedChange = null;
        this.#collapsed = null;
        if (this.#viewportResizeCleanup) {
            this.#viewportResizeCleanup();
            this.#viewportResizeCleanup = null;
        }
        if (this.#viewportScaleCleanup) {
            this.#viewportScaleCleanup();
            this.#viewportScaleCleanup = null;
        }
        if (this.#wrapper) {
            dom.removeClass(this.#wrapper, CLASS_DROPDOWN);
        }
        if (this.#menu) {
            dom.removeClass(this.#menu, CLASS_OPEN);
        }
        if (this.#trigger) {
            dom.setAttribute(this.#trigger, 'aria-expanded', 'false');
        }
        this.#unbindPositionUpdates();
        this.#clearMenuPosition();
        this.#wrapper = null;
        this.#trigger = null;
        this.#menu = null;
        this.#isOpen = false;
        this.#sidebarStateProvider = null;
        this.#alwaysDropdown = false;
        this.#collapseToFit = false;
    }

    #bindPositionUpdates(): void {
        if (this.#positionAbortController) {
            return;
        }
        const controller = new AbortController();
        const sync = (): void => this.#syncMenuPosition();
        getWindow().addEventListener('resize', sync, { signal: controller.signal });
        this.#positionScaleCleanup = this.#host.on(getWindow(), INTERFACE_SCALE_CHANGED_EVENT, sync) ?? null;
        getDocument().addEventListener('scroll', sync, { capture: true, signal: controller.signal });
        this.#positionAbortController = controller;
    }

    #unbindPositionUpdates(): void {
        this.#positionAbortController?.abort();
        this.#positionAbortController = null;
        this.#positionScaleCleanup?.();
        this.#positionScaleCleanup = null;
    }

    #clearMenuPosition(): void {
        const menu = this.#menu;
        if (!menu) {
            return;
        }
        clearPageActionsMenuPosition(menu);
    }

    #syncMenuPosition(): void {
        const menu = this.#menu;
        const trigger = this.#trigger;
        if (!menu || !trigger || !this.#isOpen) {
            return;
        }
        syncPageActionsMenuPosition(menu, trigger);
    }
}
