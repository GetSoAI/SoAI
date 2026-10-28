/* SoAI - Browser return events without duplicate focus and visibility refreshes [frontend/assets/ts/core/dom/windowReactivation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDocument, getWindow } from '@core/environment/public.ts';

const bindWindowReactivation = (reactivate: () => void): (() => void) => {
    const document = getDocument();
    const window = getWindow();
    const events = new AbortController();
    let awaitingReturn = document.visibilityState === 'hidden';
    const suspend = (): void => {
        awaitingReturn = true;
    };
    const resume = (): void => {
        if (!awaitingReturn || document.visibilityState === 'hidden') return;
        awaitingReturn = false;
        reactivate();
    };
    window.addEventListener('blur', suspend, { signal: events.signal });
    window.addEventListener('focus', resume, { signal: events.signal });
    document.addEventListener(
        'visibilitychange',
        () => {
            if (document.visibilityState === 'hidden') suspend();
            else resume();
        },
        { signal: events.signal }
    );
    return () => events.abort();
};

export { bindWindowReactivation };
