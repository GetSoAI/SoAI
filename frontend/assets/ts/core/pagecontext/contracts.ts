/* SoAI - Shared page context contracts [frontend/assets/ts/core/pagecontext/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { SanitizeUrlOptions } from '@core/security/urlSanitizer.ts';
import type { TelemetryEvent, TelemetryEventInput, TelemetryMetric, TelemetryStatus } from '@core/telemetry/contracts.ts';

type NotificationHandler = (message: string, type: NotificationType, duration: number) => void;
type ClipboardNotificationHandler = (message: string, type: NotificationType) => void;
interface StringConvertibleValue {
    toString(): string;
}
type ClipboardCopyInput = string | number | boolean | bigint | symbol | StringConvertibleValue | null | undefined | void;
type SanitizerInput = string | number | boolean | bigint | symbol | StringConvertibleValue | null | undefined | void;
type SecurityTextOptions = { allowEmpty?: boolean; trim?: boolean };

interface ClipboardCopyOptions {
    successMessage?: string;
    errorMessage?: string;
    unavailableMessage?: string;
    showNotification?: boolean;
    notify?: (message: string, type: NotificationType) => void;
    onSuccess?: () => void;
    onError?: (error: Error) => void;
}

interface ClipboardService {
    copyText: (text: ClipboardCopyInput, options?: ClipboardCopyOptions) => Promise<boolean>;
    isSupported?: () => boolean;
    registerNotificationHandler?: (handler: ClipboardNotificationHandler) => () => void;
}

interface SecurityService {
    sanitizeText: (value?: SanitizerInput, options?: SecurityTextOptions) => string;
    escapeHtml: (value?: SanitizerInput) => string;
    escapeAttribute: (value?: SanitizerInput) => string;
    sanitizeUrl: (value: SanitizerInput, options?: SanitizeUrlOptions) => string | null;
    sanitizeAbsoluteHttpUrl: (value: SanitizerInput) => string | null;
    sanitizeImageSource: (value: SanitizerInput) => string | null;
}

interface TelemetryService {
    emit: (payload: TelemetryEventInput | string) => TelemetryEvent;
    getMetric?: (name: string) => TelemetryMetric | null;
    observeMetric?: (name: string | null, handler: (metric: TelemetryMetric) => void) => () => void;
    subscribe?: (handler: (event: TelemetryEvent) => void) => () => void;
    getStatus?: () => TelemetryStatus;
}

interface ClipboardApi {
    isSupported: () => boolean;
    copyText: (text: ClipboardCopyInput, options?: ClipboardCopyOptions) => Promise<boolean>;
    registerNotificationHandler: (handler: ClipboardNotificationHandler) => () => void;
}

interface SanitizerApi {
    text: (value: SanitizerInput, options?: { allowEmpty?: boolean }) => string;
    optionalText: (value: SanitizerInput, options?: { allowEmpty?: boolean }) => string | null;
    html: (value?: SanitizerInput) => string;
    attribute: (value?: SanitizerInput) => string;
    url: (value: SanitizerInput, options?: SanitizeUrlOptions) => string | null;
    absoluteHttpUrl: (value: SanitizerInput) => string | null;
    image: (value: SanitizerInput) => string | null;
    className: (value: SanitizerInput, fallback?: string, options?: { allowEmpty?: boolean }) => string;
}

interface NotificationApi {
    show: (message: string, type?: NotificationType, duration?: number) => void;
    success: (message: string, duration?: number) => void;
    warning: (message: string, duration?: number) => void;
    error: (message: string, duration?: number) => void;
    info: (message: string, duration?: number) => void;
}

interface PageContextOptions {
    pageId: string;
    clipboard?: ClipboardService;
    sanitizer?: SecurityService;
    notifier?: NotificationHandler;
    telemetry?: TelemetryService;
}

export type { ClipboardApi, ClipboardCopyInput, ClipboardCopyOptions, ClipboardNotificationHandler, ClipboardService, NotificationApi, NotificationHandler, PageContextOptions, SanitizerApi, SanitizerInput, SecurityService, SecurityTextOptions, StringConvertibleValue, TelemetryService };
