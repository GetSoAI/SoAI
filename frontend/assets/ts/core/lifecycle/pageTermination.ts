/* SoAI - Frontend page termination lifecycle state [frontend/assets/ts/core/lifecycle/pageTermination.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getEventHub } from '@core/environment/public.ts';
import { isObject } from '@core/typeGuards.ts';

let pageTerminating = false;

const markPageTerminating = (): void => {
    pageTerminating = true;
};

const isPageTerminating = (): boolean => pageTerminating;

const isPersistedPageHideEvent = (event: Event): boolean => {
    if (!isObject(event)) {
        return false;
    }
    if (!('persisted' in event)) {
        return false;
    }
    return event.persisted === true;
};

const registerPageTerminationListeners = (): (() => void) => {
    const eventHub = getEventHub();
    const handleBeforeUnload = (): void => {
        markPageTerminating();
    };
    const handlePageHide = (event: Event): void => {
        if (isPersistedPageHideEvent(event)) {
            return;
        }
        markPageTerminating();
    };
    eventHub.addEventListener('beforeunload', handleBeforeUnload, { passive: true });
    eventHub.addEventListener('pagehide', handlePageHide, { passive: true });
    return (): void => {
        eventHub.removeEventListener('beforeunload', handleBeforeUnload);
        eventHub.removeEventListener('pagehide', handlePageHide);
    };
};

const resetPageTerminatingForTests = (): void => {
    pageTerminating = false;
};

export { isPageTerminating, markPageTerminating, registerPageTerminationListeners, resetPageTerminatingForTests };
