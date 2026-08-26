/* SoAI - Shared routing base page core validation [frontend/assets/ts/core/routing/pages/basepagecore/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';

interface ChangeDispatchTarget {
    dispatchEvent: (eventObject: Event) => boolean;
}

interface CustomValidityTarget {
    setCustomValidity: (message: string) => void;
}

const isChangeDispatchTarget = (value: EventTarget | null): value is EventTarget & ChangeDispatchTarget => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'dispatchEvent');
};

const isCustomValidityTarget = (value: Element | null): value is Element & CustomValidityTarget => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'setCustomValidity');
};

export { isChangeDispatchTarget, isCustomValidityTarget };
