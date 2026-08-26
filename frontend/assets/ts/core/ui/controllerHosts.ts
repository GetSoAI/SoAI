/* SoAI - Shared frontend UI controller hosts [frontend/assets/ts/core/ui/controllerHosts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

type NotifyType = 'success' | 'error' | 'info' | 'warning';

interface SearchHost {
    hasSearchQuery: () => boolean;
    filterSettings: () => void;
}

type DomEventHost = PageResourcesOwnerHost;

type DomMutationHost = PageDomOwnerHost;

type DomQueryHost = PageDomOwnerHost;

interface ExecutionHost extends PageFeedbackOwnerHost {
    runWithBoundary: <T>(name: string, task: () => Promise<T> | T) => Promise<T>;
    withButtonDisabled?: <T>(btn: Element, functionValue: () => Promise<T>, options?: { keepDisabled?: boolean }) => Promise<T>;
    confirmAndExecute?: <Result>(boundaryName: string, confirmOptions: ConfirmationOptions | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null) => Promise<void>;
}

type NotificationHost = PageFeedbackOwnerHost;

export type { DomEventHost, DomMutationHost, DomQueryHost, ExecutionHost, NotificationHost, NotifyType, SearchHost };
