/* SoAI - Shared routing base page layout DOM contracts [frontend/assets/ts/core/routing/pages/basepagelayout/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isRtl } from '@core/layout/direction.ts';
import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { type DOMTarget, dom } from '@core/dom/dom.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { getComputedStyleStrict, getRequestAnimationFrame } from '@core/environment/public.ts';
import { HEADER_ACTION_VISIBILITY_CLASSES } from '@core/routing/pages/pageActions.ts';
import { normalizeSelectorInput } from '@core/routing/pages/pageDom.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { waitForElementAnimations } from '@core/pageTransitions.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isArray, isElementNode, isNodeList, isString } from '@core/typeGuards.ts';
import type { BasePageLayoutState } from '@core/routing/pages/basepagelayout/state.ts';

type HeaderActionContextResolver = (context?: Element | Document | null) => Element | null;
type HeaderActionsRootResolver = () => Element | null;
const PAGE_HEADER_TIGHT_CLASS = 'page-header--tight-actions';
const PAGE_HEADER_TIGHT_STRONG_CLASS = 'page-header--tight-actions-strong';
const PAGE_HEADER_TIGHT_ENTER_PRESSURE = 1;
const PAGE_HEADER_TIGHT_RECOVERY_EXIT = 24;
const PAGE_HEADER_TIGHT_STRONG_ENTER_PRESSURE = 120;
const PAGE_HEADER_TIGHT_STRONG_EXIT_PRESSURE = 72;

const splitClassNames = (value: string | string[]): string[] => (isArray(value) ? value.flatMap(splitClassNames) : value.split(/\s+/).filter(Boolean));

const clearPageHeaderTightState = (pageHeader: HTMLElement): void => {
    pageHeader.classList.remove(PAGE_HEADER_TIGHT_CLASS, PAGE_HEADER_TIGHT_STRONG_CLASS);
};

const resolvePageHeaderTitlePressure = (pageHeader: HTMLElement, titleSection: HTMLElement, actionsWrapper: HTMLElement): { pressure: number; recoveryRoom: number } => {
    const titleRect = measureLayoutBox(titleSection);
    const actionsRect = measureLayoutBox(actionsWrapper);
    const inlineGap = isRtl(pageHeader) ? titleRect.left - actionsRect.right : actionsRect.left - titleRect.right;
    const overlap = Math.ceil(-inlineGap);
    const overflow = Math.ceil(pageHeader.scrollWidth - pageHeader.clientWidth);
    const pressure = Math.max(overlap, overflow, 0);
    const horizontalGap = Math.ceil(inlineGap);
    const widthSlack = Math.ceil(pageHeader.clientWidth - pageHeader.scrollWidth);
    const recoveryRoom = Math.max(horizontalGap, widthSlack, 0);
    return { pressure, recoveryRoom };
};

const refreshPageHeaderTitleTightStateForElement = (element: Element | null): void => {
    const pageHeader = element?.closest('.page-header');
    if (!(pageHeader instanceof HTMLElement)) {
        return;
    }
    const titleSection = dom.resolve('.page-header-title-section', pageHeader);
    const actionsWrapper = dom.resolve('.page-actions', pageHeader);
    if (!(titleSection instanceof HTMLElement) || !(actionsWrapper instanceof HTMLElement) || actionsWrapper.classList.contains('page-actions--dropdown')) {
        clearPageHeaderTightState(pageHeader);
        return;
    }
    const { pressure, recoveryRoom } = resolvePageHeaderTitlePressure(pageHeader, titleSection, actionsWrapper);
    const hasTightClass = pageHeader.classList.contains(PAGE_HEADER_TIGHT_CLASS);
    const hasStrongClass = pageHeader.classList.contains(PAGE_HEADER_TIGHT_STRONG_CLASS);
    const shouldKeepTight = hasTightClass ? pressure > 0 || recoveryRoom < PAGE_HEADER_TIGHT_RECOVERY_EXIT : pressure >= PAGE_HEADER_TIGHT_ENTER_PRESSURE;
    const shouldKeepStrong = shouldKeepTight && (hasStrongClass ? pressure >= PAGE_HEADER_TIGHT_STRONG_EXIT_PRESSURE : pressure >= PAGE_HEADER_TIGHT_STRONG_ENTER_PRESSURE);
    pageHeader.classList.toggle(PAGE_HEADER_TIGHT_CLASS, shouldKeepTight);
    pageHeader.classList.toggle(PAGE_HEADER_TIGHT_STRONG_CLASS, shouldKeepStrong);
};

const refreshPageHeaderTitleTightStateAfterActionMotion = (headerActions: HTMLElement): void => {
    const animations = headerActions.getAnimations({ subtree: true }).filter((animation) => Number.isFinite(animation.effect?.getComputedTiming().endTime));
    if (!animations.length) {
        refreshPageHeaderTitleTightStateForElement(headerActions);
        return;
    }
    terminateHandledPromise(
        waitForElementAnimations(headerActions, { ensureStarted: false, animations })
            .catch((error) => {
                if (!isAbortError(error)) errorHandler.warn('PageHeaderActions', 'Header action motion did not complete', ensureError(error));
            })
            .then(() => refreshPageHeaderTitleTightStateForElement(headerActions))
    );
};

type HeaderActionTarget = DOMTarget | readonly HeaderActionTarget[];

const getHeaderActionElements = (resolveContext: HeaderActionContextResolver, target: HeaderActionTarget, context?: Element | Document | null): Element[] => {
    const elements: Element[] = [];
    const resolutionContext = resolveContext(context);
    const collect = (candidate: HeaderActionTarget): void => {
        if (!candidate) return;
        if (isElementNode(candidate)) {
            elements.push(candidate);
            return;
        }
        if (isNodeList(candidate)) {
            for (let index = 0; index < candidate.length; index += 1) {
                const node = candidate.item(index);
                if (isElementNode(node)) {
                    elements.push(node);
                }
            }
            return;
        }
        if (isArray(candidate)) {
            candidate.forEach(collect);
            return;
        }
        if (isString(candidate)) {
            const normalized = normalizeSelectorInput(candidate);
            if (isString(normalized)) {
                elements.push(...dom.resolveAll(normalized, resolutionContext ?? undefined));
            }
        }
    };
    collect(target);
    return elements;
};

const affectsHeaderActionVisibility = (classes: string | string[]): boolean => splitClassNames(classes).some((className) => HEADER_ACTION_VISIBILITY_CLASSES.has(className));

const targetsHeaderActions = (resolveContext: HeaderActionContextResolver, target: HeaderActionTarget, context?: Element | Document | null): boolean => getHeaderActionElements(resolveContext, target, context).some((element) => Boolean(element.closest('.page-actions__menu')));

const shouldUpdateHeaderActionLayout = (resolveContext: HeaderActionContextResolver, target: HeaderActionTarget, classes: string | string[], context: Element | Document | null | undefined): boolean => targetsHeaderActions(resolveContext, target, context) && affectsHeaderActionVisibility(classes);

const refreshHeaderActionsLayout = (getHeaderActionsRoot: HeaderActionsRootResolver): void => {
    const headerActions = getHeaderActionsRoot();
    if (!(headerActions instanceof HTMLElement)) {
        return;
    }
    const actionsButton = dom.resolve('.ui-variant-accent.ui-button', headerActions);
    if (!actionsButton) {
        headerActions.classList.remove('page-actions__menu--split');
        return;
    }
    let shouldSplit = false;
    for (const child of headerActions.children) {
        if (child === actionsButton || child.classList.contains('page-header-search')) {
            continue;
        }
        if (child.classList.contains('u-hidden') || child.classList.contains('u-invisible') || child.classList.contains(CSS_CLASSES.HIDDEN) || child.getAttribute('hidden') !== null || child.getAttribute('aria-hidden') === 'true') {
            continue;
        }
        const style = getComputedStyleStrict(child);
        if (style.display !== 'none' && style.visibility !== 'hidden') {
            shouldSplit = true;
            break;
        }
    }
    headerActions.classList.toggle('page-actions__menu--split', shouldSplit);
    refreshPageHeaderTitleTightStateAfterActionMotion(headerActions);
};

const queueHeaderActionsLayoutUpdate = (state: BasePageLayoutState, resolveContext: HeaderActionContextResolver, getHeaderActionsRoot: HeaderActionsRootResolver): void => {
    if (!state.pendingHeaderActionsFrame) {
        state.pendingHeaderActionsFrame = getRequestAnimationFrame()(() => {
            state.pendingHeaderActionsFrame = null;
            resolveContext(null);
            state.pageActionsMenu?.updateDropdownState();
            refreshHeaderActionsLayout(getHeaderActionsRoot);
        });
    }
};

export { affectsHeaderActionVisibility, queueHeaderActionsLayoutUpdate, refreshHeaderActionsLayout, refreshPageHeaderTitleTightStateForElement, shouldUpdateHeaderActionLayout, targetsHeaderActions };
