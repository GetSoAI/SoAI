/* SoAI - Hardware page host factories [frontend/assets/ts/pages/hardware/controllers/hardwareHostFactories.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ElementOptions } from '@core/dom/dom.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { isHTMLElement } from '@core/typeGuards.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { SoAIBenchHistoryModalHost, SystemInfoModalHost } from '@features/hardware/public.ts';
import type { NetworkCardRendererHost } from '@pages/hardware/rendering/cards/NetworkCardRenderer.ts';
import type { StorageCardRendererHost } from '@pages/hardware/rendering/cards/StorageCardRenderer.ts';

interface HardwareCardElementFactoryDependencies {
    createElement: (tagName: string, attrs: ElementOptions, child?: string | Node) => Element;
}

interface NetworkCardHostFactoryDependencies {
    createElement: (tagName: string, options?: { className?: string }, child?: string | Node) => HTMLElement;
    updateText: (element: Element, text: string) => void;
    optionalUI: (selector: string) => Element | null;
    renderCachedContent: (container: Element, key: string, factory: () => Element | DocumentFragment) => void;
}

type StorageCardHostFactoryDependencies = NetworkCardHostFactoryDependencies;

interface HardwareCardRendererHostsFactoryDependencies {
    createElement: (tagName: string, attrs: ElementOptions, child?: string | Node) => Element;
    updateText: (element: Element, text: string) => void;
    optionalUI: (selector: string) => Element | null;
    renderCachedContent: (container: Element, key: string, factory: () => Element | DocumentFragment) => void;
}

interface SystemInfoModalHostFactoryDependencies {
    modals: ModalPresenterApi;
    domHasClass: (element: Element, className: string) => boolean;
    requireHTMLElement: (selector: string | Element, context?: Element) => HTMLElement;
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    hasClipboardSupport: () => boolean;
    copyToClipboard: (value: string, options?: { notify(message: string, type: NotificationType): void }) => Promise<void>;
    updateProperty: (target: Element, property: string, value: DomPropertyValue) => void;
    addClassName: (target: Element, className: string) => void;
    removeClassName: (target: Element, className: string) => void;
    updateText: (target: Element, text: string) => void;
    setDataAttribute: (target: Element, name: string, value: string | null) => void;
    getDataAttribute: (target: Element, name: string) => string | null;
    showNotification: (message: string, type: NotificationType, duration?: number) => void;
}

interface SoAiBenchHistoryModalHostFactoryDependencies {
    modals: ModalPresenterApi;
    downloadHistoryCsv: SoAIBenchHistoryModalHost['downloadHistoryCsv'];
    requireHTMLElement: (selector: string | Element, context?: Element) => HTMLElement;
    setHTML: SoAIBenchHistoryModalHost['setHTML'];
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    hasClipboardSupport: SoAIBenchHistoryModalHost['hasClipboardSupport'];
    copyToClipboard: SoAIBenchHistoryModalHost['copyToClipboard'];
    addClassName: (target: Element, className: string) => void;
    removeClassName: (target: Element, className: string) => void;
    updateText: (target: Element, text: string) => void;
    showNotification: SoAIBenchHistoryModalHost['showNotification'];
    getIconSync: SoAIBenchHistoryModalHost['getIconSync'];
}

function createHardwareCardElement(dependencies: HardwareCardElementFactoryDependencies, tagName: string, options?: { className?: string }, child?: string | Node): HTMLElement {
    const attrs: ElementOptions = {};
    const classNameValue = options?.className;
    if (typeof classNameValue === 'string' && classNameValue) {
        attrs['className'] = classNameValue;
    }
    const element = dependencies.createElement(tagName, attrs, child);
    if (!isHTMLElement(element)) {
        throw new Error('Expected createElement() to return an HTMLElement');
    }
    return element;
}

function createNetworkCardRendererHost(dependencies: NetworkCardHostFactoryDependencies): NetworkCardRendererHost {
    return {
        createElement: (tagName: string, options?: { className?: string }, child?: string | Node): HTMLElement => dependencies.createElement(tagName, options, child),
        updateText: (element: Element, text: string): void => dependencies.updateText(element, text),
        optionalUI: (selector: string): Element | null => dependencies.optionalUI(selector),
        renderCachedContent: (container: Element, key: string, factory: () => Element | DocumentFragment): void => dependencies.renderCachedContent(container, key, factory)
    };
}

function createStorageCardRendererHost(dependencies: StorageCardHostFactoryDependencies): StorageCardRendererHost {
    return {
        createElement: (tagName: string, options?: { className?: string }, child?: string | Node): HTMLElement => dependencies.createElement(tagName, options, child),
        updateText: (element: Element, text: string): void => dependencies.updateText(element, text),
        optionalUI: (selector: string): Element | null => dependencies.optionalUI(selector),
        renderCachedContent: (container: Element, key: string, factory: () => Element | DocumentFragment): void => dependencies.renderCachedContent(container, key, factory)
    };
}

function createHardwareCardRendererHosts(dependencies: HardwareCardRendererHostsFactoryDependencies): {
    network: NetworkCardRendererHost;
    storage: StorageCardRendererHost;
} {
    const createElement = (tagName: string, options?: { className?: string }, child?: string | Node): HTMLElement => createHardwareCardElement({ createElement: dependencies.createElement }, tagName, options, child);

    return {
        network: createNetworkCardRendererHost({
            createElement,
            updateText: dependencies.updateText,
            optionalUI: dependencies.optionalUI,
            renderCachedContent: dependencies.renderCachedContent
        }),
        storage: createStorageCardRendererHost({
            createElement,
            updateText: dependencies.updateText,
            optionalUI: dependencies.optionalUI,
            renderCachedContent: dependencies.renderCachedContent
        })
    };
}

function createSystemInfoModalHost(dependencies: SystemInfoModalHostFactoryDependencies): SystemInfoModalHost {
    return {
        modals: dependencies.modals,
        domHasClass: (element: Element, className: string): boolean => dependencies.domHasClass(element, className),
        requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => dependencies.requireHTMLElement(selector, context),
        runWithBoundary: <T>(name: string, functionValue: () => Promise<T>): Promise<T> => dependencies.runWithBoundary(name, functionValue),
        hasClipboardSupport: (): boolean => dependencies.hasClipboardSupport(),
        copyToClipboard: (value: string, options?: { notify(message: string, type: NotificationType): void }): Promise<void> => dependencies.copyToClipboard(value, options),
        updateProperty: (target: Element, property: string, value: DomPropertyValue): void => dependencies.updateProperty(target, property, value),
        addClassName: (target: Element, className: string): void => dependencies.addClassName(target, className),
        removeClassName: (target: Element, className: string): void => dependencies.removeClassName(target, className),
        updateText: (target: Element, text: string): void => dependencies.updateText(target, text),
        setDataAttribute: (target: Element, name: string, value: string | null): void => dependencies.setDataAttribute(target, name, value),
        getDataAttribute: (target: Element, name: string): string | null => dependencies.getDataAttribute(target, name),
        showNotification: (message: string, type: NotificationType, duration?: number): void => dependencies.showNotification(message, type, duration)
    };
}

function createSoAIBenchHistoryModalHost(dependencies: SoAiBenchHistoryModalHostFactoryDependencies): SoAIBenchHistoryModalHost {
    return {
        modals: dependencies.modals,
        downloadHistoryCsv: (deviceId) => dependencies.downloadHistoryCsv(deviceId),
        requireHTMLElement: (selector: string | Element, context?: Element): HTMLElement => dependencies.requireHTMLElement(selector, context),
        setHTML: (target, html): void => dependencies.setHTML(target, html),
        runWithBoundary: <T>(name: string, functionValue: () => Promise<T>): Promise<T> => dependencies.runWithBoundary(name, functionValue),
        hasClipboardSupport: (): boolean => dependencies.hasClipboardSupport(),
        copyToClipboard: (value: string, options) => dependencies.copyToClipboard(value, options),
        addClassName: (target: Element, className: string): void => dependencies.addClassName(target, className),
        removeClassName: (target: Element, className: string): void => dependencies.removeClassName(target, className),
        updateText: (target: Element, text: string): void => dependencies.updateText(target, text),
        showNotification: (message, type, duration): void => dependencies.showNotification(message, type, duration),
        getIconSync: (iconName, options) => dependencies.getIconSync(iconName, options)
    };
}

export { createHardwareCardElement, createHardwareCardRendererHosts, createNetworkCardRendererHost, createSoAIBenchHistoryModalHost, createStorageCardRendererHost, createSystemInfoModalHost };
