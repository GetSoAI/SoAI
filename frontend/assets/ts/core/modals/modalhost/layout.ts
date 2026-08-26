/* SoAI - Shared modals layout [frontend/assets/ts/core/modals/modalhost/layout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getMutationObserverCtor, getWindow } from '@core/environment/public.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { applyPosition, enforceBoundaries } from '@core/modals/modalhost/effects.ts';
import { applyFullscreenLayout, syncFullscreenButton } from '@core/modals/modalhost/eventsFullscreen.ts';
import { advanceModalLayoutGeneration, isModalLayoutCurrent } from '@core/modals/modalhost/layoutGeneration.ts';
import { resolveCenteredPosition, sanitizeSavedModalState } from '@core/modals/modalhost/layoutPolicy.ts';
import { lockPage, restorePage } from '@core/modals/modalhost/state.ts';
import { applySizeConstraints } from '@core/modals/modalhost/sizePolicy.ts';
import { applyTabsWheelScroll } from '@core/ui/controls/tabs/wheelScroll.ts';
import { synchronizeModalFrame } from '@core/modals/modalhost/geometry.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import { hideDockHint } from '@core/modals/modalhost/drag/dockHint.ts';

const cancelModalPointerInteractions = (state: ModalHostState): void => {
    for (const dragState of state.dragState.values()) {
        const modal = dragState.modalContent.closest('.ui-modal');
        const handle = modal ? dom.resolve('.modal-header-top', modal) : null;
        if (handle) dom.setStyle(handle, 'cursor', '');
    }
    state.dragState.clear();
    state.resizeState.clear();
    hideDockHint(state);
    dom.removeClass(dom.getBody(), 'resizing');
};

const reapplyFullscreenState = (state: ModalHostState, modalId: string, content: HTMLElement): void => {
    if (!state.fullscreenState.has(modalId)) {
        return;
    }
    applyFullscreenLayout(state, modalId, content, 'none');
};

const handleModalViewportChange = (state: ModalHostState): void => {
    if (state.viewportRefreshScheduled) {
        return;
    }

    state.viewportRefreshScheduled = true;
    const generation = advanceModalLayoutGeneration(state);
    state.resources.requestAnimationFrame(() => {
        state.viewportRefreshScheduled = false;
        if (state.layoutGeneration !== generation) {
            return;
        }
        if (!state.activeStack.length) {
            state.previousMobileViewportState = state.isMobileViewportState;
            return;
        }

        const shouldRecenter = state.previousMobileViewportState && state.isMobileViewportState === false;
        state.activeStack.forEach((id) => {
            const modal = dom.resolve(`#${id}`);
            if (!(modal instanceof HTMLElement)) {
                return;
            }
            synchronizeModalFrame(modal, state.isMobileViewportState);
            syncFullscreenButton(state, id, modal);
            const contentElement = modal ? dom.resolve('.modal-content', modal) : null;
            const content = contentElement instanceof HTMLElement ? contentElement : null;
            if (!content) {
                return;
            }

            const savedState = sanitizeSavedModalState(state.storage.getModalState(id));
            const config = state.registry.getConfig(id);
            const isFullscreen = state.fullscreenState.has(id);
            const layoutOverride = state.layoutOverrides.get(id);

            const size = isFullscreen
                ? null
                : applySizeConstraints({
                      content,
                      config,
                      isMobileViewport: state.isMobileViewportState,
                      savedState,
                      layoutOverride
                  });

            if (isFullscreen) {
                if (!isModalLayoutCurrent(state, id, generation)) {
                    return;
                }
                reapplyFullscreenState(state, id, content);
                return;
            }

            const sizeOverride = size ? { width: size.width, height: size.height } : null;
            if (shouldRecenter) {
                applyPosition(
                    content,
                    resolveCenteredPosition({
                        content,
                        isMobileViewport: state.isMobileViewportState,
                        sizeOverride
                    })
                );
            }

            enforceBoundaries({
                content,
                isMobileViewport: state.isMobileViewportState,
                sizeOverride
            });
        });
        state.previousMobileViewportState = state.isMobileViewportState;
    });
};

const initializeModalLayoutObservers = (state: ModalHostState): void => {
    const Observer = getMutationObserverCtor();
    if (globalThis.visualViewport) {
        state.resources.addEventListener(globalThis.visualViewport, 'resize', () => {
            handleModalViewportChange(state);
        });
    }

    const setup = (): void => {
        const body = dom.getBody();
        if (!body) {
            throw new Error('Document body must exist for modal viewport observation');
        }
        const observer = new Observer(() => {
            handleModalViewportChange(state);
        });
        observer.observe(body, { attributes: true, attributeFilter: ['class'] });
        state.resources.track(observer);
    };

    const doc = dom.getDocument();
    if (doc.readyState === 'loading') {
        state.resources.addEventListener(doc, 'DOMContentLoaded', setup, { once: true });
    } else {
        setup();
    }
};

const setupMobileViewportListener = (state: ModalHostState): void => {
    const synchronize = (): void => {
        cancelModalPointerInteractions(state);
        const matches = measureLayoutViewport().width <= state.mobileBreakpoint;
        if (matches !== state.isMobileViewportState) {
            state.previousMobileViewportState = state.isMobileViewportState;
            state.isMobileViewportState = matches;
        }
        handleModalViewportChange(state);
    };
    state.isMobileViewportState = measureLayoutViewport().width <= state.mobileBreakpoint;
    state.previousMobileViewportState = state.isMobileViewportState;
    const win = getWindow();
    state.resources.addEventListener(win, 'resize', synchronize);
    state.resources.addEventListener(win, INTERFACE_SCALE_CHANGED_EVENT, synchronize);
};

const setupModalTabsScroll = (state: ModalHostState, modal: Element): void => {
    dom.resolveAll('.tabs-nav', modal).forEach((candidate) => {
        const nav = candidate instanceof HTMLElement ? candidate : null;
        if (!nav) {
            return;
        }
        const initialized = dom.getData(nav, 'tabsWheelScroll');
        if (initialized === 'true') {
            return;
        }
        dom.setData(nav, 'tabsWheelScroll', 'true');
        state.resources.addEventListener(
            nav,
            'wheel',
            (event: Event) => {
                if (!(event instanceof WheelEvent)) {
                    return;
                }
                applyTabsWheelScroll(nav, event);
            },
            { passive: false }
        );
    });
};

const ensureResizeHandles = (content: Element): void => {
    const existing = new Set<string>();
    dom.resolveAll('.modal-resize-handle', content).forEach((handle) => {
        if (handle instanceof HTMLElement) {
            const direction = handle.dataset['direction'];
            if (direction) {
                existing.add(direction);
                return;
            }
        }
        const direction = handle.getAttribute('data-direction');
        if (direction) {
            existing.add(direction);
        }
    });

    const directions: readonly string[] = ['top', 'top-right', 'right', 'bottom-right', 'bottom', 'bottom-left', 'left', 'top-left'];
    directions.forEach((direction) => {
        if (existing.has(direction)) {
            return;
        }
        const handle = dom.getDocument().createElement('div');
        dom.addClass(handle, 'modal-resize-handle');
        dom.addClass(handle, `modal-resize-handle--${direction}`);
        handle.dataset['direction'] = direction;
        dom.appendChild(content, handle);
    });
};

const lockModalPage = (state: ModalHostState): void => {
    state.pageLockSnapshot = lockPage();
};

const restoreModalPage = (state: ModalHostState): void => {
    restorePage(state.pageLockSnapshot);
    state.pageLockSnapshot = null;
};

export { ensureResizeHandles, handleModalViewportChange, initializeModalLayoutObservers, lockModalPage, restoreModalPage, setupMobileViewportListener, setupModalTabsScroll };
