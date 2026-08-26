/* SoAI - Shared layout title manager validation [frontend/assets/ts/core/layout/header/titlemanager/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { NavigationDetail, RouterInterface, SoaiOsCapabilitiesInterface } from '@core/layout/header/titlemanager/types.ts';

const detailIsObject = (value: NavigationDetail | null): value is NavigationDetail => isObject(value);

const isRouterInterface = <T>(value: T): value is T & RouterInterface => isObject(value) && 'navigate' in value && isFunction(value.navigate);

const isSoaiOsCapabilitiesInterface = <T>(value: T): value is T & SoaiOsCapabilitiesInterface => isObject(value) && 'isSoaiOsEnabled' in value && isFunction(value.isSoaiOsEnabled);

const resolveComponent = (detail: NavigationDetail | null): string | null => {
    if (!detailIsObject(detail)) {
        return null;
    }
    if (isString(detail.pageName) && detail.pageName) {
        return detail.pageName;
    }
    if (isString(detail.component) && detail.component) {
        return detail.component;
    }
    return null;
};

export { detailIsObject, isRouterInterface, isSoaiOsCapabilitiesInterface, resolveComponent };
