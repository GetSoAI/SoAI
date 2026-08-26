/* SoAI - Plugins feature info contracts [frontend/assets/ts/features/plugins/modals/info/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

interface SecurityService {
    escapeHtml(value: string): string;
    escapeAttribute(value: string): string;
    resolveHttpsWebsiteUrl(value: string | null | undefined): string | null;
}

interface PluginCapabilityDescriptor {
    id: string;
    label: string;
    title?: string | undefined;
    className?: string | undefined;
}

interface InfoManagerHost {
    modals: ModalPresenterApi;
    requireHTMLElement(selector: string | Element, context?: Element): HTMLElement;
    optionalHTMLElement(selector: string | Element, context?: Element): HTMLElement | null;
    updateHTML(target: Element | string, html: TrustedHtml | string): void;
    copyToClipboard(text: string, options?: { notify?: (message: string, type: NotificationType) => void }): Promise<void>;
    hasClipboardSupport(): boolean;
    showNotification(message: string, type: NotificationType): void;
    sanitizeText(value: JsonValue | null | undefined, options?: Record<string, JsonValue | null | undefined>): string;
    sanitizeClassName(value: JsonValue | null | undefined, fallback: string | Record<string, JsonValue | null | undefined>, mapping?: Record<string, JsonValue | null | undefined>): string;
}

interface InfoManagerOptions {
    host: InfoManagerHost;
    security: SecurityService;
    getCapabilityDescriptors: (plugin: PluginRecord) => readonly PluginCapabilityDescriptor[];
}

interface InfoState {
    currentInfoPlugin: PluginRecord | null;
}

export type { InfoManagerHost, InfoManagerOptions, InfoState, PluginCapabilityDescriptor, SecurityService };
