/* SoAI - Shared layout header interface [frontend/assets/ts/core/layout/HeaderInterface.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';

type ClockFormat = '12h' | '24h';
type HeaderServiceValue = WeakKey | null;
type HeaderEscapableValue = string | HeaderServiceValue | undefined;
type HeaderServiceGuard<T extends HeaderServiceValue> = (value: HeaderServiceValue) => value is T;

interface HeaderServiceResolver {
    (serviceId: string): HeaderServiceValue;
    <T extends HeaderServiceValue>(serviceId: string, guard: HeaderServiceGuard<T>, label?: string | undefined): T;
}

interface IconOptions {
    size?: string | number;
    strokeWidth?: string | number;
}

interface IconApplyConfig {
    element: HTMLElement | null;
    selector?: string;
    icon: string;
    replace?: boolean;
}

interface StorageService {
    getClockFormat: () => ClockFormat;
    setClockFormat: (format: ClockFormat) => void;
    getHeaderClockEnabled: () => boolean;
    getClockSecondsEnabled: () => boolean;
    getTheme: () => string | null;
    setTheme: (theme: string) => void;
    addRecentSearch: (query: string) => void;
}

interface IconsService {
    reset: () => void;
    get: (name: string, options?: IconOptions) => TrustedHtml | undefined;
    apply: (targets: IconApplyConfig[]) => Promise<void>;
}

interface LayoutFrameManager {
    queue: (callback: () => void) => void;
    cancel: () => void;
}

interface SearchController {
    onNavigation: (component: string | null) => void;
    collapse: (options?: { blur?: boolean }) => void;
}

interface TitleController {
    brand: string;
    currentTitle: string;
    handleLocalizationChange: () => void;
    refreshDisplayedTitle: () => void;
    updateDocumentTitle: (value: string) => void;
}

interface SettingsMenuController {
    hide: () => void;
}

interface UserMenuController {
    hide: () => void;
}

interface ThemeController {
    handleThemeEvent: (theme: string | undefined) => void;
}

interface ClockController {
    refresh: () => void;
}

interface RestartReminderController {
    initialize: () => Promise<void>;
    destroy: () => void;
    localize: () => void;
}

interface LicensingShortcutController {
    initialize: () => void;
    destroy: () => void;
}

interface AccountController {
    initialize: () => Promise<void>;
    destroy: () => void;
    localize: () => void;
}

interface ResponsiveController {
    refresh: () => void;
}

interface ActionZoneController {
    initialize: () => Promise<void>;
    destroy: () => void;
    localize: () => void;
}

export interface HeaderControllers {
    actions: ActionZoneController;
    search: SearchController;
    menu: SettingsMenuController;
    user: UserMenuController;
    theme: ThemeController;
    clock: ClockController;
    restart: RestartReminderController;
    licensing: LicensingShortcutController;
    account: AccountController;
    responsive: ResponsiveController;
    title: TitleController;
}

export interface HeaderInterface {
    on(target: EventTarget, event: string, handler: (event: Event) => void): (() => void) | void;

    getDom(key: string): HTMLElement | null;
    getDomMany(keys: string[]): (HTMLElement | null)[];
    optionalUI(selector: string, context?: Element): Element | null;
    optionalHTMLElement(selector: string, context?: Element): HTMLElement | null;
    requireHTMLElement(selector: string, context?: Element): HTMLElement;

    updateText(element: Element, text: string): void;
    updateHTML(element: HTMLElement, html: TrustedHtml | string, options: { escape: boolean }): void;
    updateAttribute(element: Element, attr: string, value: string): void;
    updateProperty(element: HTMLElement, property: string, value: DomPropertyValue): void;
    addClassName(element: Element, className: string | string[]): void;
    removeClassName(element: Element, className: string | string[]): void;

    setTimer(callback: () => void, delay: number, options?: { repeat?: boolean | undefined }): number | null;
    clearTimer(id: number | null): void;

    resolveService: HeaderServiceResolver;
    getStorage(): StorageService;

    getClockFormat(): ClockFormat;
    setClockFormat(format: ClockFormat): void;
    closeDropdowns(options?: { except?: string | string[] | undefined }): void;
    handleLogout(): Promise<void>;
    isMobilePortrait(): boolean;
    updateLogosForTheme(): void;

    escape(value: HeaderEscapableValue): string;
    logger(level: string, message: string, data?: TelemetryValue): void;

    readonly icons: IconsService;
    readonly controllers: HeaderControllers;
    readonly hiddenClass: string;
    readonly layoutFrameManager: LayoutFrameManager | null;
}

export type { ClockFormat, HeaderEscapableValue, HeaderServiceGuard, HeaderServiceResolver, HeaderServiceValue, IconOptions, IconApplyConfig, StorageService, IconsService, LayoutFrameManager };
export type { SearchController, TitleController, SettingsMenuController, UserMenuController, ThemeController, ClockController, RestartReminderController, LicensingShortcutController, AccountController, ResponsiveController, ActionZoneController };
