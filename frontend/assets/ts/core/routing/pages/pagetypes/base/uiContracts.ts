/* SoAI - Shared routing UI contracts [frontend/assets/ts/core/routing/pages/pagetypes/base/uiContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue, JsonRecord } from '@core/types/jsonValues.ts';
import type { LanguageEntryWithFlag } from '@core/languageservice/types.ts';

export interface SetUIValueOptions {
    formatter?: (value: JsonValue | null | undefined, element: Element) => JsonValue | null | undefined;
    attribute?: string;
    allowNull?: boolean;
    data?: Record<string, string> | null;
    toggle?: boolean | null;
    element?: Element | null;
    skipChangeEvent?: boolean | undefined;
}

export interface RunPageTaskOptions<T = JsonValue | null | undefined> {
    loadingElement?: Element | string;
    loadingText?: string;
    successMessage?: string;
    errorToastMessage?: string;
    onSuccess?: (result: T) => Promise<void> | void;
    onError?: (error: Error) => Promise<void> | void;
    onFinally?: () => Promise<void> | void;
    rethrow?: boolean;
    displayName?: string;
    telemetryModuleId?: string;
    telemetryContext?: Record<string, JsonValue | null | undefined>;
    telemetryTags?: string | string[];
}

export interface SetBusyOptions {
    className?: string;
    disable?: boolean;
    customValidity?: { busy: string };
}

export interface AttachViewportResizeOptions {
    debounceMs?: number | null;
    options?: AddEventListenerOptions;
}

export interface UnsavedChangesGuardOptions {
    hasUnsavedChanges: () => boolean;
    confirmMessage: string;
    guardId?: string;
}

export interface CanvasPrepareResult {
    canvas: HTMLCanvasElement;
    context: CanvasRenderingContext2D;
    width: number;
    height: number;
}

export interface LanguageService {
    initialize: () => Promise<void>;
    setLanguage: (code: string) => Promise<void>;
    getLanguage: () => string;
    getAvailableLanguages: () => ReadonlyArray<LanguageEntryWithFlag>;
    getLocale: () => string;
    getTranslation: (key: string, langCode?: string | null) => string | null;
    interpolate: (template: string, parameters: JsonRecord) => string;
    plural(key: string, count: number, parameters?: JsonRecord): string;
    formatNumber(number: number, options?: Intl.NumberFormatOptions): string;
    formatDate(date: Date | number | string, options?: Intl.DateTimeFormatOptions): string;
}

export interface PageAutoResourceState {
    status: 'offline' | 'ready' | 'error';
    error?: { baseUrl?: string; message?: string };
}
