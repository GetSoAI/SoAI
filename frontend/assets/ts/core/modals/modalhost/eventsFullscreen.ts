/* SoAI - Shared modals events fullscreen [frontend/assets/ts/core/modals/modalhost/eventsFullscreen.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODAL_HEADER_CLOSE_SELECTOR, MODAL_HEADER_FULLSCREEN_SELECTOR, createModalHeaderButtonElement, renderModalHeaderButtonIcon } from '@core/modals/headerButtons.ts';
import { applyPosition, clampPosition, getTransformTranslate } from '@core/modals/modalhost/effects.ts';
import { advanceModalLayoutGeneration, isModalLayoutCurrent } from '@core/modals/modalhost/layoutGeneration.ts';
import { resolveContentSizeLimits } from '@core/modals/modalhost/sizePolicy.ts';
import { shouldShowFullscreenControl } from '@core/modals/modalhost/layoutPolicy.ts';
import type { ModalHostState } from '@core/modals/modalhost/contracts.ts';
import type { Position } from '@core/modals/types.ts';

const EXPAND_ICON = 'modal-expand';
const RESTORE_ICON = 'modal-restore';
const TRANSITION_DURATION_MS = 150;

const resolveFullscreenTransition = (content: HTMLElement): string => {
    const duration = scaleAnimationDurationMs(TRANSITION_DURATION_MS, content);
    return `width ${duration}ms ease, height ${duration}ms ease, transform ${duration}ms ease`;
};

const getModalElement = (id: string): Element | null => {
    const modalId = id ? id.trim() : '';
    return modalId ? dom.resolve(`#${modalId}`) : null;
};

const applyFullscreenLayout = (state: ModalHostState, modalId: string, content: HTMLElement, transition: string): boolean => {
    const config = state.registry.getConfig(modalId);
    if (!config || !config.allowFullscreen) {
        return false;
    }

    const limits = resolveContentSizeLimits(content, config, state.isMobileViewportState);
    const bounded = clampPosition({
        content,
        position: { x: 0, y: 0 },
        isMobileViewport: state.isMobileViewportState,
        sizeOverride: { width: limits.maxWidth, height: limits.maxHeight }
    });

    dom.setStyle(content, 'transition', transition);
    dom.setStyles(content, {
        width: `${limits.maxWidth}px`,
        height: `${limits.maxHeight}px`,
        minWidth: `${limits.minWidth}px`,
        minHeight: `${limits.minHeight}px`,
        maxWidth: `${limits.maxWidth}px`,
        maxHeight: `${limits.maxHeight}px`
    });
    applyPosition(content, bounded);
    dom.addClass(content, 'is-fullscreen');
    return true;
};

const toggleFullscreen = (state: ModalHostState, modalId: string): boolean => {
    const modalElement = getModalElement(modalId);
    if (!modalElement || !(modalElement instanceof HTMLElement)) {
        return false;
    }

    const config = state.registry.getConfig(modalId);
    if (!config || !shouldShowFullscreenControl(config, state.isMobileViewportState)) {
        return false;
    }

    const isFullscreen = state.fullscreenState.has(modalId);
    const content = dom.resolve('.modal-content', modalElement);
    const toggleButton = dom.resolve(MODAL_HEADER_FULLSCREEN_SELECTOR, modalElement);

    if (!content || !toggleButton || !(content instanceof HTMLElement) || !(toggleButton instanceof HTMLElement)) {
        return false;
    }

    if (isFullscreen) {
        exitFullscreen(state, modalId, content, toggleButton);
        return false;
    } else {
        enterFullscreen(state, modalId, content, toggleButton);
        return true;
    }
};

const enterFullscreen = (state: ModalHostState, modalId: string, content: HTMLElement, toggleButton: HTMLElement): void => {
    const currentPosition = getTransformTranslate(content);
    const generation = advanceModalLayoutGeneration(state);

    state.fullscreenState.set(modalId, {
        previousPosition: currentPosition !== null ? currentPosition : { x: 0, y: 0 },
        previousSize: { width: content.offsetWidth, height: content.offsetHeight }
    });

    state.resources.requestAnimationFrame(() => {
        if (!isModalLayoutCurrent(state, modalId, generation)) {
            return;
        }
        if (!state.fullscreenState.has(modalId)) {
            return;
        }
        applyFullscreenLayout(state, modalId, content, resolveFullscreenTransition(content));
    });

    const icon = renderModalHeaderButtonIcon(RESTORE_ICON, { width: 18, height: 18 });
    dom.setHTML(toggleButton, icon, { escape: false });
};

const exitFullscreen = (state: ModalHostState, modalId: string, content: HTMLElement, toggleButton: HTMLElement, immediate = false, forcedPosition?: Position): void => {
    const savedState = state.fullscreenState.get(modalId);
    if (!savedState) {
        return;
    }
    const generation = advanceModalLayoutGeneration(state);

    dom.setStyle(content, 'transition', immediate ? 'none' : resolveFullscreenTransition(content));
    const restoredPosition = forcedPosition ?? savedState.previousPosition;
    const restoredX = restoredPosition.x;
    const restoredY = restoredPosition.y;

    const hasForcedPosition = forcedPosition !== undefined;
    const restoreStyles = (): void => {
        if (!isModalLayoutCurrent(state, modalId, generation)) {
            return;
        }
        const transition = resolveFullscreenTransition(content);
        dom.setStyles(content, {
            width: `${savedState.previousSize.width}px`,
            height: `${savedState.previousSize.height}px`
        });
        applyPosition(content, { x: restoredX, y: restoredY });
        if (immediate && !hasForcedPosition) {
            dom.setStyle(content, 'transition', transition);
        }
        if (immediate && hasForcedPosition) {
            state.resources.requestAnimationFrame(() => {
                if (!isModalLayoutCurrent(state, modalId, generation)) {
                    return;
                }
                dom.setStyle(content, 'transition', transition);
            });
        }
    };

    dom.removeClass(content, 'is-fullscreen');

    if (immediate) {
        restoreStyles();
    } else {
        state.resources.requestAnimationFrame(restoreStyles);
    }

    const icon = renderModalHeaderButtonIcon(EXPAND_ICON, { width: 18, height: 18 });
    dom.setHTML(toggleButton, icon, { escape: false });

    state.fullscreenState.delete(modalId);
    state.storage.setModalState(modalId, { size: { width: savedState.previousSize.width, height: savedState.previousSize.height } });
};

const syncFullscreenButton = (state: ModalHostState, modalId: string, modalElement: HTMLElement): void => {
    const config = state.registry.getConfig(modalId);
    if (!config || !shouldShowFullscreenControl(config, state.isMobileViewportState)) {
        const existingToggle = dom.resolve(MODAL_HEADER_FULLSCREEN_SELECTOR, modalElement);
        if (existingToggle instanceof HTMLElement) {
            existingToggle.remove();
        }
        return;
    }

    const closeButton = dom.resolve(MODAL_HEADER_CLOSE_SELECTOR, modalElement);
    if (!closeButton || !(closeButton instanceof HTMLElement)) {
        return;
    }

    const existingToggle = dom.resolve(MODAL_HEADER_FULLSCREEN_SELECTOR, modalElement);
    if (existingToggle) {
        return;
    }

    const toggleLabel = i18n.t('common.fullscreen.toggle');
    const toggleButton = createModalHeaderButtonElement({ role: 'fullscreen', label: toggleLabel, modalId });
    closeButton.after(toggleButton);
};

export { applyFullscreenLayout, exitFullscreen, syncFullscreenButton, toggleFullscreen };
