/* SoAI - Shared layout title manager contracts [frontend/assets/ts/core/layout/header/titlemanager/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HeaderServiceResolver } from '@core/layout/HeaderInterface.ts';

interface TitleManagerHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    resolveService: HeaderServiceResolver;
    getDom: (key: string) => HTMLElement | null;
    optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null;
    updateText: (element: Element, text: string) => void;
    updateAttribute: (element: Element, attr: string, value: string) => void;
    isMobilePortrait: () => boolean;
    onSearchNavigation: (component: string | null) => void;
}

interface NavigationDetail {
    pageName?: string | null | undefined;
    component?: string | null | undefined;
    title?: string | null | undefined;
}

interface RouterInterface {
    navigate: (route: string) => Promise<void>;
}

interface SoaiOsCapabilitiesInterface {
    isSoaiOsEnabled: () => boolean;
}

interface TitleManagerOptions {
    header: TitleManagerHost;
    dynamicComponents?: Set<string> | undefined;
}

interface SetHeaderCollapsedOptions {
    force?: boolean | undefined;
}

interface SetCurrentPageTitleOptions {
    force?: boolean | undefined;
}

type TitleNavigationDirection = 'up' | 'down' | 'none';

export type { NavigationDetail, RouterInterface, SetCurrentPageTitleOptions, SetHeaderCollapsedOptions, SoaiOsCapabilitiesInterface, TitleManagerHost, TitleManagerOptions, TitleNavigationDirection };
