/* SoAI - Shared layout search manager validation [frontend/assets/ts/core/layout/header/searchmanager/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject } from '@core/typeGuards.ts';
import type { SearchManagerHost, RouterInterface, SearchPanelInterface, StatusManagerInterface } from '@core/layout/header/searchmanager/types.ts';

const isRouterInterface = <T>(value: T): value is T & RouterInterface => isObject(value) && 'navigate' in value && isFunction(value.navigate) && 'navigateWithQuery' in value && isFunction(value.navigateWithQuery);

const isSearchPanelInterface = <T>(value: T): value is T & SearchPanelInterface => isObject(value) && 'initialize' in value && isFunction(value.initialize) && 'search' in value && isFunction(value.search) && 'searchFiles' in value && isFunction(value.searchFiles) && 'openPromptPreview' in value && isFunction(value.openPromptPreview);

const isStatusManagerInterface = <T>(value: T): value is T & StatusManagerInterface => isObject(value) && 'createIndicator' in value && isFunction(value.createIndicator);

const isSearchManagerHost = <T>(value: T): value is T & SearchManagerHost => isObject(value) && 'on' in value && isFunction(value.on) && 'getDom' in value && isFunction(value.getDom) && 'closeDropdowns' in value && isFunction(value.closeDropdowns) && 'resolveService' in value && isFunction(value.resolveService);

export { isRouterInterface, isSearchManagerHost, isSearchPanelInterface, isStatusManagerInterface };
