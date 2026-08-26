/* SoAI - Shared layout settings menu manager contracts [frontend/assets/ts/core/layout/header/settingsmenumanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { HeaderServiceResolver } from '@core/layout/HeaderInterface.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';

interface SettingsMenuManagerHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getDomMany: (keys: string[]) => (HTMLElement | null)[];
    closeDropdowns: (options?: { except?: string | string[] | undefined }) => void;
    logger: (level: string, message: string, data?: TelemetryValue) => void;
    updateText: (element: Element, text: string) => void;
    updateAttribute: (element: Element, attr: string, value: string) => void;
    handleLogout: () => Promise<void>;
    resolveService: HeaderServiceResolver;
}

const MENU_ITEM_KEYS: readonly string[] = Object.freeze(['logs', 'settings', 'updates', 'about', 'logout']);

interface Router {
    navigate(page: string): Promise<void>;
    navigateWithQuery(page: string, query: Record<string, string>): void;
}

interface ErrorHandlerInterface {
    warn(context: string, message: string, error?: Error): void;
}

interface MenuItemEntry {
    key: string;
    element: HTMLElement | null;
    action: () => void;
}

const isRouter = <T>(value: T): value is T & Router => isObject(value) && 'navigate' in value && isFunction(value.navigate) && 'navigateWithQuery' in value && isFunction(value.navigateWithQuery);

export type { ErrorHandlerInterface, MenuItemEntry, Router, SettingsMenuManagerHost };
export { MENU_ITEM_KEYS, isRouter };
