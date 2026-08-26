/* SoAI - Shared routing router internals [frontend/assets/ts/core/routing/router/routerInternals.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { renderNavigationError } from '@core/routing/router/pageOutlet.ts';
import type { ElementOptions, ReplaceContentOptions } from '@core/dom/types.ts';
import type { SidebarServiceContract } from '@core/routing/router/routerDependencies.ts';
import { hasFunctionProperty, isBoolean, isHTMLElement, isObject, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

interface DomRenderer {
    createFragmentFromNodes: (children?: Node | NodeList | string | null | undefined) => DocumentFragment;
    create: (tag: string, attrs?: ElementOptions) => Element;
    replaceContent: (container: Element, content: DocumentFragment | string, options?: ReplaceContentOptions) => void;
    getBody: () => HTMLElement;
    getDocument: () => Document;
}

const resolveContainerTarget = (getUI: (selector: string, context?: Element | Document | null) => Element | null, containerTarget: string | HTMLElement | null | undefined): HTMLElement | null => {
    if (!containerTarget) return null;
    if (isHTMLElement(containerTarget)) return containerTarget;
    if (!isString(containerTarget)) return null;
    const target = toTrimmedString(containerTarget);
    if (!target) return null;
    const selector = target.startsWith('#') || target.startsWith('.') ? target : `#${target}`;
    const found = getUI(selector);
    return isHTMLElement(found) ? found : null;
};

const renderRouterError = (dom: DomRenderer, contentContainer: HTMLElement | null, type: string, message: string, reloadHandler: () => void): void => {
    let resolvedContainer = contentContainer;
    if (!resolvedContainer) {
        try {
            resolvedContainer = dom.getBody();
        } catch (error) {
            ensureError(error);
            const doc = dom.getDocument();
            resolvedContainer = doc.body;
        }
    }
    if (!resolvedContainer) {
        throw new Error('Router error container is unavailable');
    }
    renderNavigationError(dom, resolvedContainer, type, message, reloadHandler);
};

const isSidebarServiceContract = <T>(value: T): value is T & SidebarServiceContract => {
    if (!isObject(value)) return false;
    if (!hasFunctionProperty(value, 'setActiveByPage')) return false;
    if (!('initialized' in value)) return true;
    const initializedValue = value['initialized'];
    return initializedValue === undefined || isBoolean(initializedValue);
};

const resolveSidebarService = <T>(getSidebarService: () => T | null, isSidebarService: (value: T | null) => boolean): T | null => {
    const candidate = getSidebarService();
    if (!isSidebarService(candidate)) return null;
    return candidate;
};

export { isSidebarServiceContract, renderRouterError, resolveContainerTarget, resolveSidebarService };
