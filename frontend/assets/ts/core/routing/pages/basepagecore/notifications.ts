/* SoAI - Shared routing notifications [frontend/assets/ts/core/routing/pages/basepagecore/notifications.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { loadingState } from '@core/loadingState.ts';
import { request, requestFunctionValue } from '@core/routing/pages/basepagecore/actions.ts';

type PageLoadingHandle = ReturnType<typeof loadingState.show>;

const showPageLoadingHandle = (pageLoadingState: typeof loadingState, message: string): PageLoadingHandle => {
    return requestFunctionValue(request(pageLoadingState, 'BasePage.loadingState'), 'show', 'BasePage.loadingState')(message);
};

const hidePageLoadingHandle = (pageLoadingState: typeof loadingState, handle: PageLoadingHandle | null): void => {
    requestFunctionValue(request(pageLoadingState, 'BasePage.loadingState'), 'hide', 'BasePage.loadingState')(handle);
};

const withPageLoadingHandle = async <T>(pageLoadingState: typeof loadingState, message: string, operation: () => Promise<T>): Promise<T> => {
    const handle = showPageLoadingHandle(pageLoadingState, message);
    try {
        return await operation();
    } finally {
        hidePageLoadingHandle(pageLoadingState, handle);
    }
};

export { hidePageLoadingHandle, showPageLoadingHandle, withPageLoadingHandle };
export type { PageLoadingHandle };
