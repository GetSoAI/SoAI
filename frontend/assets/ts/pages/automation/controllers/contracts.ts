/* SoAI - Automation page controllers contracts [frontend/assets/ts/pages/automation/controllers/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { AutomationRunActivityServiceContract, AutomationDataService } from '@features/automation/public.ts';
import type { AutomationInitialSelection, AutomationUiRefs } from '@pages/automation/types.ts';

interface ControllerRuntimeDependencies {
    ui: AutomationUiRefs;
    storage: StorageService;
    api: ApiClient;
    dataService: AutomationDataService;
    initialSelection: AutomationInitialSelection | null;
    runActivity: AutomationRunActivityServiceContract;
    requireHTMLElement: (selector: string, context?: Element | Document | null) => HTMLElement;
    replaceElementContent: (element: Element, content: string | TrustedHtml, options?: { escape?: boolean }) => void;
    flushDOMUpdates: () => void;
    getIconSync: (icon: IconName, options?: IconOptions) => TrustedHtml;
    showNotification: (message: string, type?: NotificationType, duration?: number) => void;
    navigateToConversation: (conversationId: string) => void;
    modalPresenter: ModalPresenterApi;
    getStyleProp: (property: string, element?: Element) => string;
    requestAnimationFrame: (callback: () => void) => number;
    setTimeout: (callback: () => void, delay: number) => number | null;
    clearTimer: (timerId: number | null | undefined) => void;
    runWithBoundary: <T>(operation: string, task: () => Promise<T> | T) => Promise<T>;
}

interface ControllerDependencies extends Pick<ControllerRuntimeDependencies, 'api' | 'dataService' | 'initialSelection' | 'modalPresenter' | 'runActivity' | 'storage' | 'ui'> {
    feedback: PageFeedback;
    pageDom: PageDom;
    pageLifecycle: PageLifecycle;
    pageResources: PageResources;
    router: Router;
    services: PageServices;
}

export type { ControllerDependencies, ControllerRuntimeDependencies };
