/* SoAI - Plugin configuration modal contracts [frontend/assets/ts/features/plugins/modals/config/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareSnapshotOptions } from '@core/api/types/hardware.ts';
import type { HardwareSnapshotResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { BaseClassNames } from '@core/ui/classNames.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ConfigUpdateResponse } from '@core/api/contracts/configContracts.ts';

interface SecurityService {
    escapeHtml(value: string): string;
    escapeAttribute(value: string): string;
}

interface ConfigurationManager {
    initialize(config: JsonObject): void;
    onChange(callback: () => void): () => void;
    getValue(key: string): JsonValue;
    getValueByPath(data: JsonValue, key: string): JsonValue;
    areValuesEqual(current: JsonValue | undefined, original: JsonValue | undefined): boolean;
    updateValue(key: string, value: JsonValue): void;
    hasChanges: boolean;
    currentData: JsonObject;
    originalData: JsonObject;
    commitChanges(): void;
}

interface ConfigsApi {
    get(name: string): Promise<JsonObject>;
    update(name: string, data: JsonObject): Promise<ConfigUpdateResponse>;
}

interface HardwareApi {
    snapshot(options?: HardwareSnapshotOptions): Promise<HardwareSnapshotResponse>;
}

interface ConfigManagerHost {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    queryUI(selector: string | Element | string[], context?: Element): Element[];
    showNotification(message: string, type?: NotificationType, duration?: number): void;
    on(target: EventTarget | Element, event: string, handler: EventListener, options?: AddEventListenerOptions): () => void;
    updateHTML(target: Element | string, html: TrustedHtml | string): void;
    updateText(target: Element | string, text: string): void;
    updateProperty(target: Element | string, property: string, value: DomPropertyValue): void;
    toggleClassName(target: Element | string, className: string, force?: boolean | null): void;
    setTimeout(callback: (() => void) | undefined, delay: number): number | null;
    clearTimer(timerId: number | null | undefined): void;
    createConfigurationManager(): ConfigurationManager;
    api: { configs: ConfigsApi; hardware: HardwareApi };
}

interface ConfigManagerOptions {
    host: ConfigManagerHost;
    classNames: BaseClassNames;
    security: SecurityService;
}

interface ConfigState {
    configuringPlugin: PluginRecord | null;
}

type ConfigFieldInputType = 'boolean' | 'json' | 'number' | 'string';
type ConfigStructuredFieldType = 'array' | 'object';

interface ConfigFieldMetadata {
    key: string;
    type: ConfigFieldInputType;
    structuredType: ConfigStructuredFieldType | null;
    validationId: string | null;
}

export type { ConfigurationManager, ConfigFieldInputType, ConfigFieldMetadata, ConfigManagerHost, ConfigManagerOptions, ConfigState, ConfigStructuredFieldType, ConfigsApi, HardwareApi, SecurityService };
