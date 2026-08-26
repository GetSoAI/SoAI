/* SoAI - Shared layout header state [frontend/assets/ts/core/layout/header/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { HeaderControllers } from '@core/layout/HeaderInterface.ts';

type HeaderDomKey = 'header' | 'searchContainer' | 'searchInput' | 'searchButton' | 'searchDropdown' | 'notificationButton' | 'notificationCenter' | 'settingsButton' | 'settingsDropdown' | 'userButton' | 'userDropdown' | 'userWrapper' | 'clockButton' | 'clockTime' | 'clockDate' | 'pageTitle' | 'hamburger' | 'actionZone';

type ClockFormat = '12h' | '24h';
type ClockDisplayMode = 'digital' | 'analog';

interface HeaderIconOptions {
    size?: string | number | undefined;
    strokeWidth?: string | number | undefined;
}

interface HeaderController {
    initialize?: (() => void | Promise<void>) | undefined;
    destroy?: (() => void) | undefined;
    localize?: (() => void) | undefined;
}

interface CloseDropdownsOptions {
    except?: string | string[] | undefined;
}

interface CustomEventDetail {
    theme?: JsonValue | undefined;
    format?: JsonValue | undefined;
}

interface HeaderControllerBundle {
    controllers: HeaderControllers;
    order: HeaderController[];
}

const HEADER_SELECTORS: Record<HeaderDomKey, string> = Object.freeze({
    header: '.header',
    searchContainer: '#header-search-container',
    searchInput: '#header-search-input',
    searchButton: '.header-search__button',
    searchDropdown: '#search-dropdown',
    notificationButton: '#notification-button',
    notificationCenter: '#header-notification-center',
    settingsButton: '#settings-button',
    settingsDropdown: '#settings-dropdown',
    userButton: '#user-button',
    userDropdown: '#user-dropdown',
    userWrapper: '.user-wrapper',
    clockButton: '.clock-button',
    clockTime: '.clock-time',
    clockDate: '.clock-date',
    pageTitle: '#page-title',
    hamburger: '#hamburger-menu',
    actionZone: '#header-action-zone'
});

const HEADER_DOM_KEYS: ReadonlySet<string> = new Set(Object.keys(HEADER_SELECTORS));

const isHeaderDomKey = (value: string): value is HeaderDomKey => HEADER_DOM_KEYS.has(value);

const DYNAMIC_TITLE_COMPONENTS: Set<string> = new Set(['dashboard', 'about', 'chat', 'terminal', 'automation']);

export { DYNAMIC_TITLE_COMPONENTS, HEADER_SELECTORS, isHeaderDomKey, HEADER_DOM_KEYS };
export type { HeaderDomKey, ClockFormat, ClockDisplayMode, HeaderIconOptions, HeaderController, CloseDropdownsOptions, CustomEventDetail, HeaderControllerBundle };
