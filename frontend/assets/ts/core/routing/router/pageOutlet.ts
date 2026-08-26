/* SoAI - Shared routing page outlet [frontend/assets/ts/core/routing/router/pageOutlet.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { emitNavigationEvent, NAVIGATION_EVENTS, type NavigationEventDetail } from '@core/navigationEvents.ts';
import { toLowerCase, toTrimmedString } from '@core/normalize.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError, extractErrorMessage } from '@core/errors/coerce.ts';
import type { ElementOptions, ReplaceContentOptions } from '@core/dom/types.ts';
import type { NavigationDetail, RouteDefinition, RouteParameters, SidebarComponentTargets } from '@core/routing/router/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { hasOwn, isFunction, isHTMLElement, isObject, isString } from '@core/typeGuards.ts';

interface RouterLifecycleDependencies {
    dom: { getBody: () => HTMLElement };
    stateManager: { setTabState: (key: string, value: JsonValue | null | undefined) => void };
    cleanupManager: { cleanupAll: () => Promise<void> };
    closeOpenModals: () => number;
    queryUI: (selector: string) => Element[];
    emitRouterEvent: (stage: string, data?: Record<string, string | null>, severity?: string) => void;
}

interface DomRenderer {
    createFragmentFromNodes: () => DocumentFragment;
    create: (tag: string, attrs?: ElementOptions) => Element;
    replaceContent: (container: Element, content: DocumentFragment | string, options?: ReplaceContentOptions) => void;
}

const createReloadHandler =
    (getLocation: () => Location): (() => void) =>
    () => {
        const loc = getLocation();
        if (!isFunction(loc.reload)) throw new Error('Location.reload must be available');
        loc.reload();
    };

const renderNavigationError = (dom: DomRenderer, contentContainer: HTMLElement, type: string, message: string, reloadHandler: () => void): void => {
    let title: string;
    if (type === 'navigation') {
        title = i18n.t('router.errors.navigation');
    } else if (type === 'load') {
        title = i18n.t('router.errors.load');
    } else {
        title = i18n.t('router.errors.critical');
    }

    const frag = dom.createFragmentFromNodes();
    const div = dom.create('div', { className: 'error-message' });
    const h2 = dom.create('h2', { textContent: title });
    const resolvedMessage = toTrimmedString(message) || i18n.t('router.errors.unknown');
    const point = dom.create('p', { textContent: resolvedMessage });
    const btn = dom.create('button', {
        type: 'button',
        className: 'ui-button ui-variant-accent',
        textContent: i18n.t('router.errors.refreshPage')
    });
    btn.addEventListener('click', reloadHandler);
    div.append(h2, point, btn);
    frag.appendChild(div);

    dom.replaceContent(contentContainer, frag, { escape: false });

    const text = isHTMLElement(point) ? point.textContent : null;
    throw new Error(`${title}: ${text ?? ''}`);
};

const performNavigationCleanup = async (dependencies: RouterLifecycleDependencies, currentRoute: string | null): Promise<void> => {
    dependencies.emitRouterEvent('cleanup:start', { route: currentRoute });
    dependencies.closeOpenModals();
    dependencies.emitRouterEvent('cleanup:complete', { route: currentRoute });
};

const buildNavigationDetail = (route: RouteDefinition, parameters: RouteParameters, phase: string, error: Error | null): NavigationDetail => ({
    route: route.path,
    component: route.component,
    title: route.getTitle(),
    parameters,
    dataRequirements: route.data ?? null,
    phase,
    resolvedRoute: route,
    resolvedParameters: parameters,
    timestamp: Date.now(),
    error: error ? { message: extractErrorMessage(error) } : null
});

const buildPersistedNavigationDetail = (detail: NavigationDetail): JsonObject => ({
    route: detail.route,
    component: detail.component,
    title: detail.title,
    parameters: { ...detail.parameters },
    dataRequirements: detail.dataRequirements
        ? {
              streams: [...detail.dataRequirements.streams],
              resources: [...detail.dataRequirements.resources],
              collections: [...detail.dataRequirements.collections]
          }
        : null,
    phase: detail.phase,
    resolvedRoute: detail.resolvedRoute ? detail.resolvedRoute.path : null,
    resolvedParameters: detail.resolvedParameters ? { ...detail.resolvedParameters } : null,
    timestamp: detail.timestamp,
    error: detail.error
});

const dispatchNavigationEvent = (dependencies: RouterLifecycleDependencies, route: RouteDefinition, parameters: RouteParameters, phase: string, error: Error | null): NavigationDetail => {
    const detail = buildNavigationDetail(route, parameters, phase, error);

    const eventName = phase === 'start' ? NAVIGATION_EVENTS.START : phase === 'error' ? NAVIGATION_EVENTS.ERROR : NAVIGATION_EVENTS.COMPLETE;
    const eventDetail: NavigationEventDetail = { ...detail };
    emitNavigationEvent(eventName, eventDetail);

    if (eventName === NAVIGATION_EVENTS.COMPLETE) {
        dependencies.stateManager.setTabState('navigation', buildPersistedNavigationDetail(detail));
        dependencies.stateManager.setTabState('activePage', detail.component);
    }
    return detail;
};

const pushRouteState = (historyApi: History, targetPath: string, title: string, replaceState: boolean): void => {
    historyApi[replaceState ? 'replaceState' : 'pushState']({ route: targetPath }, title, `#${targetPath}`);
};

const updateBodyPageClass = (dependencies: RouterLifecycleDependencies, route: RouteDefinition): void => {
    const componentName = toTrimmedString(route.component);
    if (!componentName || !isString(componentName)) return;
    let body: HTMLElement;
    try {
        body = dependencies.dom.getBody();
    } catch (error) {
        throw ensureError(error);
    }
    if (!body || !isObject(body.classList)) return;

    const remove = Array.from(body.classList).filter((cls) => cls.startsWith('page-'));
    if (remove.length) body.classList.remove(...remove);
    body.classList.add(`page-${toLowerCase(componentName).replace(/[^a-z0-9]+/g, '-')}`);

    const scope = toTrimmedString(componentName);
    if (scope) {
        body.setAttribute('data-page-scope', scope);
    } else {
        body.removeAttribute('data-page-scope');
    }

    if (route.layout.scrollToTopAction === false) {
        body.setAttribute('data-scroll-top-action', 'disabled');
    } else {
        body.removeAttribute('data-scroll-top-action');
    }
};

const updateSidebarActiveState = (componentName: string, sidebarTargets: SidebarComponentTargets, sidebarService: { initialized?: boolean; setActiveByPage?: (page: string) => void } | null): void => {
    if (!isString(componentName) || !componentName) {
        throw new Error('Router cannot update sidebar without a component name');
    }
    if (!sidebarService || !isFunction(sidebarService.setActiveByPage)) return;
    if ('initialized' in sidebarService && sidebarService.initialized !== true) return;

    const mapped = hasOwn(sidebarTargets, componentName) ? sidebarTargets[componentName] : null;
    sidebarService.setActiveByPage(isString(mapped) && mapped ? mapped : componentName);
};

export { createReloadHandler, performNavigationCleanup, pushRouteState, renderNavigationError, dispatchNavigationEvent, updateBodyPageClass, updateSidebarActiveState };

export type { RouterLifecycleDependencies };
