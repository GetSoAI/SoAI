/* SoAI - Virtual model modal integration [frontend/assets/ts/pages/models/controllers/page/modalintegration/virtualModelsManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isElementNode, isHTMLElement, isObject } from '@core/typeGuards.ts';
import type { UiPreferences, VirtualModelStrategy } from '@core/storage/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { VirtualModelsManager, type VirtualModelsHost } from '@features/models/public.ts';
import type { ModelsModalRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import { resolveModelsItemCardId } from '@pages/models/controllers/modelsModelProperties.ts';

interface VirtualModelsIntegrationRoots {
    virtualModelsModalRoot: Element;
    virtualModelEditModalRoot: Element;
}

interface VirtualModelsIntegrationModelProperties {
    formatStrategyLabel(strategy: JsonValue | null | undefined): string;
}

interface VirtualModelStrategyStorage {
    getPreferences: () => UiPreferences;
    setPreference: (key: string, value: VirtualModelStrategy) => UiPreferences;
}

const resolveVirtualMatches = (pageDom: PageDom, roots: VirtualModelsIntegrationRoots, selector: string | Element | string[], context?: Element): Element[] => {
    if (context) {
        return pageDom.query(selector, context);
    }
    if (isElementNode(selector)) {
        return [selector];
    }
    return [...pageDom.query(selector, roots.virtualModelEditModalRoot), ...pageDom.query(selector, roots.virtualModelsModalRoot)];
};

const resolveVirtualRequiredUi = (pageDom: PageDom, roots: VirtualModelsIntegrationRoots, selector: string | Element, context?: Element): Element => {
    const matches = resolveVirtualMatches(pageDom, roots, selector, context);
    const element = matches[0];
    if (!element || matches.length !== 1) {
        throw new Error(`ModelsPage required UI missing or ambiguous: ${String(selector)}`);
    }
    return element;
};

const resolveVirtualRequiredHTMLElement = (pageDom: PageDom, roots: VirtualModelsIntegrationRoots, selector: string | Element, context?: Element): HTMLElement => {
    const element = resolveVirtualRequiredUi(pageDom, roots, selector, context);
    if (!isHTMLElement(element)) {
        throw new Error(`ModelsPage required HTMLElement must be an HTMLElement: ${String(selector)}`);
    }
    return element;
};

const isVirtualModelStrategyStorage = <T>(value: T): value is T & VirtualModelStrategyStorage => isObject(value) && hasFunctionProperty(value, 'getPreferences') && hasFunctionProperty(value, 'setPreference');

const requireStrategyStorage = <T>(storage: T): T & VirtualModelStrategyStorage => {
    if (!isVirtualModelStrategyStorage(storage)) {
        throw new Error('Virtual models manager requires core.storage.getPreferences/setPreference');
    }
    return storage;
};

const readLastVirtualModelStrategy = (storage: VirtualModelStrategyStorage): VirtualModelStrategy => {
    const preferences = storage.getPreferences();
    const stored = preferences.lastVirtualModelStrategy;
    if (stored === 'failover' || stored === 'load_balancing') {
        return stored;
    }
    return 'load_balancing';
};

const createVirtualModelsManager = (runtime: ModelsModalRuntimeDependencies, roots: VirtualModelsIntegrationRoots, modelProperties: VirtualModelsIntegrationModelProperties): VirtualModelsManager => {
    const { infrastructure, collection } = runtime;
    const strategyStorage = requireStrategyStorage(infrastructure.storage);
    const virtualModelsHost: VirtualModelsHost = {
        view: {
            modals: infrastructure.services.modals,
            requireHTMLElement: (selector, context) => resolveVirtualRequiredHTMLElement(infrastructure.pageDom, roots, selector, context),
            requireUI: (selector, context) => resolveVirtualRequiredUi(infrastructure.pageDom, roots, selector, context),
            queryUI: (selector, context) => resolveVirtualMatches(infrastructure.pageDom, roots, selector, context),
            showNotification: (message, type, options) => infrastructure.feedback.show(message, type, options),
            dom: infrastructure.dom,
            sanitizer: infrastructure.sanitizer,
            setUIValue: (target, value, options) => {
                const normalizedValue = value === null || value === undefined ? value : infrastructure.sanitizer.text(value, { allowEmpty: true });
                if (typeof target === 'string') {
                    const element = resolveVirtualRequiredUi(infrastructure.pageDom, roots, target);
                    infrastructure.pageElements.setValue(element, normalizedValue, options);
                    return;
                }
                infrastructure.pageElements.setValue(target, normalizedValue, options);
            },
            updateHTML: (target, html) => {
                if (typeof target === 'string') {
                    const element = resolveVirtualRequiredUi(infrastructure.pageDom, roots, target);
                    infrastructure.pageDom.updateHtml(element, html);
                    return;
                }
                infrastructure.pageDom.updateHtml(target, html);
            },
            updateText: (target, text) => {
                if (typeof target === 'string') {
                    const element = resolveVirtualRequiredUi(infrastructure.pageDom, roots, target);
                    infrastructure.pageDom.updateText(element, text);
                    return;
                }
                infrastructure.pageDom.updateText(target, text);
            },
            toggleClassName: (target, className, force) => {
                const normalizedForce = typeof force === 'boolean' ? force : undefined;
                if (typeof target === 'string') {
                    const element = resolveVirtualRequiredUi(infrastructure.pageDom, roots, target);
                    infrastructure.pageDom.toggleClass(element, className, normalizedForce);
                    return;
                }
                infrastructure.pageDom.toggleClass(target, className, normalizedForce);
            },
            addClassName: (target, classes) => {
                if (typeof target === 'string') {
                    const element = resolveVirtualRequiredUi(infrastructure.pageDom, roots, target);
                    infrastructure.pageDom.addClass(element, classes);
                    return;
                }
                infrastructure.pageDom.addClass(target, classes);
            }
        },
        data: {
            api: infrastructure.api,
            getCollection: () => collection.collections.runtime,
            requireStreamSubscriptions: () => infrastructure.streaming.runtime().subscriptions,
            on: (target, event, handler, options) => infrastructure.pageResources.on(target, event, handler, options),
            removeItemById: (identifier, options) => collection.removeItemById(identifier, options),
            getItemCardId: (item) => {
                const identifier = resolveModelsItemCardId(item);
                if (!identifier) {
                    throw new Error('Virtual models manager requires a model identifier');
                }
                return identifier;
            }
        },
        preferences: {
            formatStrategyLabel: (strategy) => modelProperties.formatStrategyLabel(strategy),
            getLastVirtualModelStrategy: () => readLastVirtualModelStrategy(strategyStorage),
            setLastVirtualModelStrategy: (value) => {
                strategyStorage.setPreference('last_virtual_model_strategy', value);
            }
        }
    };
    return new VirtualModelsManager({ host: virtualModelsHost });
};

export { createVirtualModelsManager };
export type { VirtualModelsIntegrationModelProperties, VirtualModelsIntegrationRoots };
