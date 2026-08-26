/* SoAI - Shared layout header rendering [frontend/assets/ts/core/layout/header/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { IconApplyConfig } from '@core/layout/HeaderInterface.ts';

const createHeaderIconTargets = (options: { searchContainer: HTMLElement | null; searchButton: HTMLElement | null; notificationButton: HTMLElement | null; settingsButton: HTMLElement | null; userButton: HTMLElement | null }): IconApplyConfig[] => [
    { element: options.searchContainer, selector: '.header-search__icon', icon: 'search' },
    { element: options.searchButton, selector: 'span, svg', icon: 'search', replace: true },
    { element: options.notificationButton, selector: '.ui-icon, svg', icon: 'bell' },
    { element: options.settingsButton, selector: '.ui-icon, svg', icon: 'settings' },
    { element: options.userButton, selector: '.ui-icon, svg', icon: 'user' }
];

export { createHeaderIconTargets };
