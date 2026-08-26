/* SoAI - Shared routing base page collections events [frontend/assets/ts/core/routing/pages/basepagecollections/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { scaleAnimationDurationMs } from '@core/animations/speed.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { resolve } from '@core/dom/dom.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { err, request } from '@core/routing/pages/basepagecore/actions.ts';
import type { CollapseApplyOptions, CollapseController, CollapseControllerOptions } from '@core/routing/pages/pagetypes/public.ts';
import { isElementNode, isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { BasePageCollectionsStorageContract } from '@core/routing/pages/basepagecollections/contracts.ts';

interface CollapsibleCardDependencies {
    pageDom: PageDom;
    pageElements: PageUi;
    resources: PageResources;
    storage: BasePageCollectionsStorageContract;
}

interface CollapsibleCardState {
    controllers: Map<string, CollapseController>;
}

const configureCardCollapse = (dependencies: CollapsibleCardDependencies, state: CollapsibleCardState, options: CollapseControllerOptions = {}): CollapseController => {
    const { card: cardRoot, selector: selectorValue, contentSelector: contentSelector = '[data-card-content]', contentElement: contentElementValue, titleBarSelector = '.card-title-bar', persistKey: persistKey, key: keyValue, collapsedClass = CSS_CLASSES.COLLAPSED, hiddenClass = CSS_CLASSES.HIDDEN, contentCollapsedClass: contentCollapsedClass, guardSelector: guardSelector = 'button, a, input, select, textarea, label, [data-ignore-collapse]', toggleButtonCollapsedClass = 'rotated', animate = true, animationDuration = 320, animationEasing = 'ease', ...rest } = options;

    const cardTarget = cardRoot ?? selectorValue;
    if (!cardTarget) {
        throw err('Card selector/element required');
    }

    const cardElement = dependencies.pageElements.resolveElement(cardTarget);
    if (!cardElement) {
        throw err('Card element missing');
    }

    const titleBar = resolve(titleBarSelector, cardElement);
    if (!titleBar) {
        throw err('Title bar missing');
    }

    const contentElement = !isNullOrUndefined(contentElementValue) ? dependencies.pageElements.resolveElement(contentElementValue) : resolve(contentSelector, cardElement);
    if (!contentElement) {
        throw err('Content missing');
    }
    if (!(contentElement instanceof HTMLElement)) {
        throw err('Content element must be an HTMLElement');
    }

    const toggleButton = rest.toggleButtonSelector ? (cardElement.matches(rest.toggleButtonSelector) ? cardElement : resolve(rest.toggleButtonSelector, cardElement)) : null;
    const persistStorageKey = persistKey || (cardElement instanceof HTMLElement ? cardElement.dataset['collapseKey'] : null);
    const storage = persistStorageKey ? request(dependencies.storage, 'Storage') : null;
    const cardKey = keyValue || persistStorageKey || cardElement.id || `card-${state.controllers.size + 1}`;
    const persistedValue = storage && persistStorageKey ? storage.get(persistStorageKey) : undefined;
    let isCollapsed = Boolean(rest.initialCollapsed ?? persistedValue ?? cardElement.classList.contains(collapsedClass));

    dependencies.pageDom.addClass(titleBar, 'clickable');
    const computedDisplay = getComputedStyleStrict(contentElement).display;
    const defaultDisplay = (computedDisplay !== 'none' ? computedDisplay : contentElement.dataset['defaultDisplay']) || 'block';
    contentElement.dataset['defaultDisplay'] = defaultDisplay;
    const scaledAnimationDuration = scaleAnimationDurationMs(animationDuration, contentElement);
    const scaledOpacityDuration = scaleAnimationDurationMs(Math.max(120, animationDuration - 80), contentElement);
    const collapseTransition = `max-height ${scaledAnimationDuration}ms ${animationEasing}, opacity ${scaledOpacityDuration}ms ${animationEasing}`;
    if (animate) {
        contentElement.dataset['collapseTransition'] = collapseTransition;
    }

    let collapseEndHandler: (() => void) | undefined;
    const raf = (callback: FrameRequestCallback): number => dependencies.resources.tracker.requestAnimationFrame(callback);
    const applyCollapse = (collapsed: boolean, { persist: persistState = true, skip: skipTransition = false, force: forceState = false }: CollapseApplyOptions = {}): boolean => {
        const targetCollapsed = Boolean(collapsed);
        if (!forceState && targetCollapsed === isCollapsed) {
            return isCollapsed;
        }
        if (isFunction(collapseEndHandler)) {
            collapseEndHandler();
        }

        const runTransition = animate && !skipTransition;
        dependencies.pageDom.updateStyle(contentElement, 'transition', runTransition ? collapseTransition : 'none');
        dependencies.pageDom.toggleClass(contentElement, hiddenClass, false);
        dependencies.pageDom.updateStyle(contentElement, 'display', defaultDisplay);

        const finalize = (finalCollapsed: boolean): void => {
            if (isCollapsed !== finalCollapsed) {
                return;
            }
            dependencies.pageDom.updateStyles(contentElement, { maxHeight: 'none', opacity: '1', overflow: '' });
            if (finalCollapsed) {
                dependencies.pageDom.toggleClass(contentElement, hiddenClass, true);
                dependencies.pageDom.updateStyle(contentElement, 'display', 'none');
            }
            if (animate) {
                dependencies.pageDom.updateStyle(contentElement, 'transition', collapseTransition);
            }
            collapseEndHandler = undefined;
        };

        dependencies.pageDom.toggleClass(cardElement, collapsedClass, targetCollapsed);
        if (contentCollapsedClass) {
            dependencies.pageDom.toggleClass(contentElement, contentCollapsedClass, targetCollapsed);
        }
        dependencies.pageDom.updateAttribute(contentElement, 'aria-hidden', String(targetCollapsed));
        dependencies.pageDom.updateAttribute(titleBar, 'aria-expanded', String(!targetCollapsed));
        if (toggleButton) {
            dependencies.pageDom.toggleClass(toggleButton, toggleButtonCollapsedClass, targetCollapsed);
            dependencies.pageDom.updateAttribute(toggleButton, 'aria-expanded', String(!targetCollapsed));
        }
        dependencies.pageDom.updateStyle(contentElement, 'overflow', 'hidden');

        if (runTransition) {
            dependencies.pageDom.updateStyles(contentElement, {
                maxHeight: `${targetCollapsed ? contentElement.scrollHeight : 0}px`,
                opacity: targetCollapsed ? '1' : '0'
            });
            raf(() =>
                dependencies.pageDom.updateStyles(contentElement, {
                    maxHeight: `${targetCollapsed ? 0 : contentElement.scrollHeight}px`,
                    opacity: targetCollapsed ? '0' : '1'
                })
            );
            collapseEndHandler = dependencies.resources.on(contentElement, 'transitionend', (event: Event) => event.target === contentElement && finalize(targetCollapsed), {
                once: true
            });
        } else {
            finalize(targetCollapsed);
        }

        (targetCollapsed ? rest.onCollapse : rest.onExpand)?.();
        isCollapsed = targetCollapsed;
        rest.onStateChange?.(targetCollapsed);
        if (persistState && storage && persistStorageKey) {
            storage.set(persistStorageKey, targetCollapsed);
        }
        return targetCollapsed;
    };

    const initialize = (value: boolean): void => {
        applyCollapse(value, { persist: false, skip: true, force: true });
        if (isFunction(rest.onReady)) {
            rest.onReady(value);
        }
    };

    if (rest.noInitialize !== true) {
        initialize(isCollapsed);
    }

    const controller: CollapseController = {
        key: cardKey,
        element: cardElement,
        card: cardElement,
        container: contentElement,
        content: contentElement,
        titleBar,
        toggleButton,
        isCollapsed: () => isCollapsed,
        apply: applyCollapse,
        collapse: () => applyCollapse(true),
        expand: () => applyCollapse(false),
        toggle: () => applyCollapse(!isCollapsed),
        refresh: () => applyCollapse(isCollapsed, { persist: false, skip: true, force: true })
    };

    dependencies.resources.on(titleBar, 'click', (event: Event) => (!guardSelector || !(isElementNode(event.target) && event.target.closest(guardSelector))) && controller.toggle());
    if (rest.enableKeyboard !== false) {
        dependencies.resources.on(titleBar, 'keydown', (event: Event) => {
            if (!(event instanceof KeyboardEvent)) {
                return;
            }
            if (event.key !== 'Enter' && event.key !== ' ') {
                return;
            }
            event.preventDefault();
            controller.toggle();
        });
    }
    if (toggleButton) {
        dependencies.resources.on(toggleButton, 'click', (event: Event) => {
            event.preventDefault();
            event.stopPropagation();
            controller.toggle();
        });
    }

    state.controllers.set(cardKey, controller);
    return controller;
};

export { configureCardCollapse };
export type { CollapsibleCardDependencies, CollapsibleCardState };
