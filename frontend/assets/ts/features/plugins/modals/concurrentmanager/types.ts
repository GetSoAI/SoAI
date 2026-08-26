/* SoAI - Plugins feature concurrent manager contracts [frontend/assets/ts/features/plugins/modals/concurrentmanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { AcceptedPowerActionResponse } from '@core/api/contracts/powerContracts.ts';
import type { ConfigUpdateResponse } from '@core/api/contracts/configContracts.ts';

type ConcurrentRestartOperationType = 'restart-application';

interface ConcurrentSliderBounds {
    min: number;
    defaultMax: number;
    maxLimit: number;
}

interface ConcurrentApiConfigs {
    update(name: string, config: JsonObject): Promise<ConfigUpdateResponse>;
}

interface ConcurrentApiSystemPower {
    restartApplication?: () => Promise<AcceptedPowerActionResponse>;
}

interface ConcurrentApiSystem {
    power?: ConcurrentApiSystemPower;
}

interface ConcurrentApi {
    configs: ConcurrentApiConfigs;
    system?: ConcurrentApiSystem;
}

interface ConcurrentModalViewPort {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    updateProperty(target: Element | string, property: string, value: DomPropertyValue): void;
    updateAttribute(target: Element | string, attribute: string, value: string | null): void;
    addClassName(target: Element | string, classes: string | string[]): void;
    removeClassName(target: Element | string, classes: string | string[]): void;
    updateText(target: Element | string, text: string): void;
    toggleClassName(target: Element | string, className: string, force?: boolean | null): void;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    showNotification(message: string, type?: NotificationType, duration?: number): void;
    on(target: EventTarget | Element, event: string, handler: EventListener, options?: AddEventListenerOptions): () => void;
}

interface ConcurrentSettingsStatePort {
    getMaxConcurrentPlugins(): number | null;
    setMaxConcurrentPlugins(value: number | null): void;
    getConcurrentPluginsOriginalValue(): number | null;
    setConcurrentPluginsOriginalValue(value: number | null): void;
    getCoreConfigCache(): JsonObject | null;
    setCoreConfigCache(value: JsonObject | null): void;
    updateStats(): void;
}

interface ConcurrentSettingsOperationsPort {
    loadCoreConfig(options?: { force?: boolean }): Promise<void>;
    getRestartOverlay: () => { show: (type: ConcurrentRestartOperationType) => void };
    api: ConcurrentApi;
}

interface ConcurrentManagerHost {
    view: ConcurrentModalViewPort;
    state: ConcurrentSettingsStatePort;
    operations: ConcurrentSettingsOperationsPort;
}

export type { ConcurrentManagerHost, ConcurrentRestartOperationType, ConcurrentSliderBounds };
