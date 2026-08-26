/* SoAI - Shared routing collections actions [frontend/assets/ts/core/routing/pages/collections/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isHTMLElement } from '@core/typeGuards.ts';
import type { ActionHandlerConfig, CollectionEventBindingContext, DelegatedHandlerConfig } from '@core/routing/pages/collections/types.ts';

interface NormalizedActionHandler {
    selector: string;
    handler: (eventObject: Event) => void;
    event: string;
    preventDefault: boolean;
    stopPropagation: boolean;
    optional: boolean;
}

interface NormalizedDelegatedHandler {
    container: string;
    selector: string;
    handler: (eventObject: Event, target: Element) => void;
    event: string;
}

const normalizeActionHandler = (config: ActionHandlerConfig | null): NormalizedActionHandler | null => {
    if (!config) {
        return null;
    }

    const { selector, handler, event = 'click', preventDefault = false, stopPropagation = false, optional = false } = config;

    if (!selector || !isFunction(handler)) {
        return null;
    }

    return { selector, handler, event, preventDefault, stopPropagation, optional };
};

const normalizeDelegatedHandler = (config: DelegatedHandlerConfig | null): NormalizedDelegatedHandler | null => {
    if (!config) {
        return null;
    }
    const { container, selector, handler, event = 'click' } = config;
    if (!container || !selector || !isFunction(handler)) {
        return null;
    }
    return { container, selector, handler, event };
};

const resolveActionRoot = (context: CollectionEventBindingContext, targets: Element[]): HTMLElement => {
    let resolvedSection: HTMLElement | null = null;
    for (const target of targets) {
        const section = target.closest('[data-section]');
        if (isHTMLElement(section)) {
            if (resolvedSection && resolvedSection !== section) {
                throw new Error('CollectionManager action targets must share one page section');
            }
            resolvedSection = section;
        }
    }
    if (resolvedSection) {
        return resolvedSection;
    }
    const hostContainer = context.resolveHostContainer();
    if (isHTMLElement(hostContainer)) {
        return hostContainer;
    }
    throw new Error('CollectionManager requires a stable root for action bindings');
};

const resolveMatchingTarget = (root: Element, eventTarget: EventTarget | null, selector: string): Element | null => {
    if (!(eventTarget instanceof Element)) {
        return null;
    }
    const matched = eventTarget.closest(selector);
    if (!matched || !root.contains(matched)) {
        return null;
    }
    return matched;
};

const bindActionGroup = (context: CollectionEventBindingContext, root: HTMLElement, handlers: NormalizedActionHandler[], eventName: string): void => {
    context.on(root, eventName, (eventObject: Event): void => {
        for (const config of handlers) {
            if (config.event !== eventName) {
                continue;
            }
            const actionTarget = resolveMatchingTarget(root, eventObject.target, config.selector);
            if (!actionTarget) {
                continue;
            }
            if (config.preventDefault) {
                eventObject.preventDefault();
            }
            if (config.stopPropagation) {
                eventObject.stopPropagation();
                eventObject.stopImmediatePropagation();
            }
            config.handler(eventObject);
            return;
        }
    });
};

const bindActionHandlers = (context: CollectionEventBindingContext, handlers: ActionHandlerConfig[] = []): void => {
    const normalizedHandlers: NormalizedActionHandler[] = [];
    const rootTargets: Element[] = [];
    for (const config of handlers) {
        const normalized = normalizeActionHandler(config);
        if (!normalized) {
            continue;
        }
        const elements = context.query(normalized.selector);
        if (!elements || elements.length === 0) {
            if (!normalized.optional) {
                throw new Error(`CollectionManager missing action targets for ${normalized.selector}`);
            }
        } else {
            rootTargets.push(...elements);
        }
        normalizedHandlers.push(normalized);
    }

    if (!normalizedHandlers.length) {
        return;
    }
    const root = resolveActionRoot(context, rootTargets);
    const eventNames = Array.from(new Set(normalizedHandlers.map((handler) => handler.event)));
    for (const eventName of eventNames) {
        bindActionGroup(context, root, normalizedHandlers, eventName);
    }
};

const bindDelegatedHandlers = (context: CollectionEventBindingContext, configs: DelegatedHandlerConfig[] = []): void => {
    for (const config of configs) {
        const normalized = normalizeDelegatedHandler(config);
        if (!normalized) {
            continue;
        }

        const { container, selector, event, handler } = normalized;
        const containers = context.query(container);
        if (!containers || containers.length === 0) {
            throw new Error(`CollectionManager missing delegated container for ${container}`);
        }

        containers.forEach((containerElement) => {
            const targets = context.query(selector, containerElement);
            for (const target of targets) {
                if (!(target instanceof HTMLElement)) {
                    throw new TypeError('Delegated target must be an HTMLElement');
                }
            }
            context.on(containerElement, event, (eventObject: Event): void => {
                const target = resolveMatchingTarget(containerElement, eventObject.target, selector);
                if (!target) {
                    return;
                }
                handler(eventObject, target);
            });
        });
    }
};
export { bindActionHandlers, bindDelegatedHandlers };
