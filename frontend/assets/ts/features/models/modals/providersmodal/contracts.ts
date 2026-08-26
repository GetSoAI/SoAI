/* SoAI - Providers modal manager contracts [frontend/assets/ts/features/models/modals/providersmodal/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { ExternalProviderRecord } from '@core/api/contracts/pluginProviderContracts.ts';
import type { ProviderStatusUpdatedEvent } from '@core/realtime/eventcontracts/providerContracts.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface ProviderData {
    id: string;
    name: string;
    pluginName: string;
    revision: number;
    apiUrl: string;
    lastStatus: ProviderAvailabilityStatus;
    lastError: string | null;
    lastCheckedAtMs: number | null;
    availability: ProviderAvailabilityPresentation;
}

type ProviderAvailabilityStatus = 'UNCHECKED' | 'OK' | 'ERROR' | 'TIMEOUT' | 'VALIDATING' | 'AUTH_REQUIRED';

type ProviderAvailabilityTone = 'neutral' | 'success' | 'danger' | 'warning' | 'loading';

interface ProviderAvailabilityPresentation {
    statusLabel: string;
    statusClassName: string;
    checkedLabel: string;
    errorLabel: string;
    tone: ProviderAvailabilityTone;
}

interface LoadProvidersOptions {
    focusPlugin?: string;
}

type ProvidersManagerDependencies = {
    modals: ModalPresenterApi;
    optionalUI: (selector: string, context?: Element) => Element | null;
    queryUI: (selector: string | Element | string[], context?: Element) => Element[];
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
    updateHTML: (element: Element, html: TrustedHtml | string, options?: { escape?: boolean }) => void;
    addClassName: (target: string | Element, className: string, context?: Element) => void;
    removeClassName: (target: string | Element, className: string, context?: Element) => void;
    consumeInitialActionContext: () => { action?: string; plugin?: string; vm?: string } | null;
    loadPlugins: (options?: { force?: boolean }) => Promise<PluginRecord[]>;
    getActiveProviderPlugins: () => PluginRecord[];
    deleteProvider: (pluginName: string, providerId: string, revision: number) => Promise<void>;
    getData: (element: Element, key: string) => string | null;
    requestProviders: (pluginName: string, signal?: AbortSignal) => Promise<ExternalProviderRecord[]>;
    subscribeProviderUpdate: (callback: (payload: ProviderStatusUpdatedEvent) => void) => () => void;
    requestAnimationFrame: (callback: FrameRequestCallback) => number;
    setTimer: (callback: () => void, delayMs: number) => number | null;
    clearTimer: (timerId: number | null) => void;
    sanitizer: Pick<SanitizerApi, 'attribute' | 'html'>;
};

export type { LoadProvidersOptions, ProviderAvailabilityPresentation, ProviderAvailabilityStatus, ProviderAvailabilityTone, ProviderData, ProvidersManagerDependencies };
