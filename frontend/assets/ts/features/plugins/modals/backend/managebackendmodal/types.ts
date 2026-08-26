/* SoAI - Plugins feature manage backend modal contracts [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BackendVariantsResponse, PluginBackendUpdatesResponse, PluginBackendUpdateStatus } from '@core/api/contracts/pluginManagementContracts.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { BackendManagerSecurity, BackendOperationHost, BackendStatusIndicatorApi } from '@features/plugins/modals/backend/backendTypes.ts';

interface ManageClassNames {
    hidden: string;
    disabled: string;
}

interface ManageState {
    currentPlugin: PluginRecord | null;
    updateInfo: PluginBackendUpdateStatus | null;
    backendVariantsReady: boolean;
}

interface ManageBackendViewPort {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    on(target: EventTarget | Element, event: string, handler: EventListener, options?: AddEventListenerOptions): () => void;
    updateText(target: Element | string, text: string): void;
    updateHTML(target: Element | string, html: TrustedHtml | string, options?: { escape?: boolean; context?: Element | Document | null }): void;
    updateProperty(target: Element | string, property: string, value: DomPropertyValue): void;
    updateAttribute(target: Element | string, attribute: string, value: string | null): void;
    addClassName(target: Element | string, classes: string | string[]): void;
    removeClassName(target: Element | string, classes: string | string[]): void;
    toggleClassName(target: Element | string, className: string, force?: boolean | null): void;
    setDataAttribute(target: Element | string, name: string, value: string | null): void;
    dom: { getData(element: Element, key: string): string | null };
}

interface ManageBackendPolicyPort {
    checkBackendInstallationSupport(plugin: PluginRecord): boolean;
    isPluginPermanentlyDisabled(plugin: PluginRecord): boolean;
    notifyPluginIncompatible(plugin: PluginRecord): void;
}

interface ManageBackendStatusPort {
    getBackendStatus(plugin: PluginRecord): string;
    getBackendVersion(plugin: PluginRecord): string;
    getPluginStatus(plugin: PluginRecord): string;
    handleBackendWebsiteLinkClick(event: Event): Promise<void>;
    getStatusManager(): BackendStatusIndicatorApi | null;
    subscribeModalLedUpdates(): void;
    unsubscribeModalLedUpdates(): void;
    setCurrentManagingPlugin(plugin: PluginRecord | null): void;
    setCurrentUpdateInfo(info: PluginBackendUpdateStatus | null): void;
    normalizeVersion(value: JsonValue | null | undefined): { raw: string | null; safe: string | null };
}

interface ManageBackendOperationsPort extends BackendOperationHost {
    checkUpdates(): Promise<PluginBackendUpdatesResponse>;
    getBackendVariants(pluginName: string): Promise<BackendVariantsResponse>;
    saveBackendVariantSelection(pluginName: string, variantId: string): Promise<BackendVariantsResponse>;
}

interface ManageBackendManagerHost {
    view: ManageBackendViewPort;
    policy: ManageBackendPolicyPort;
    status: ManageBackendStatusPort;
    operations: ManageBackendOperationsPort;
}

interface BackendManagerDependencies {
    host: ManageBackendManagerHost;
    classNames: ManageClassNames;
    security: BackendManagerSecurity;
}

export type { BackendManagerDependencies, ManageBackendManagerHost, ManageClassNames, ManageState };
