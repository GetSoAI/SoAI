/* SoAI - Settings page control layer boundary contracts [frontend/assets/ts/pages/settings/controllers/page/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import type { RestartOverlayService, SettingsPageState } from '@pages/settings/controllers/page/state.ts';
import type { ConfirmationOptions } from '@core/ui/modals/dialogs/types.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ApiClient } from '@core/api/service.ts';
import type { AuthManager } from '@core/auth/public.ts';
import type { LanguageService } from '@core/routing/pages/pagetypes/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { dom } from '@core/dom/dom.ts';
import type { SettingsEditionContribution } from '@core/edition/settingsContribution.ts';
import type { NormalTabDefinition } from '@core/settings/contracts.ts';

interface SettingsPageDependencies {
    restartOverlay: RestartOverlayService;
    product: SettingsEditionContribution | null;
    dashboardTitle: (() => string) | null;
}

interface SettingsRuntimeOwners extends PageLayoutOwnerHost, PageStreamingOwnerHost, PageServicesOwnerHost, PageUiOwnerHost, PageLifecycleOwnerHost, PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    api: ApiClient;
    auth: AuthManager;
    languageService: LanguageService;
    storage: StorageService;
    router: Router;
    dom: typeof dom;
    pageContext: PageContext;
}

interface SettingsRuntimeContext {
    owners: SettingsRuntimeOwners;
    edition: {
        product: SettingsEditionContribution | null;
        dashboardTitle: (() => string) | null;
        normalTabs: readonly NormalTabDefinition[];
    };
    controls: {
        getSearchQuery(): string | null;
        setSearchQuery(value: string): void;
        isDestroyed(): boolean;
    };
}

interface SettingsManagerCallbacks {
    filterSettings: () => void;
    withButtonDisabled: <T>(button: Element | null, functionValue: () => Promise<T>, options?: { keepDisabled?: boolean }) => Promise<T>;
    confirmAndExecute: <Result>(boundaryName: string, confirmOptions: ConfirmationOptions | null, action: () => Promise<Result>, successMessage: string | null, onSuccess: (() => Promise<void> | void) | null, onError: ((error: Error) => void) | null) => Promise<void>;
    updatePreferenceToggleLabel: (element: Element, checked?: boolean) => void;
    warnAndFocus: (element: Element | null, message: string) => void;
    applyWallpaperOverlay: (value: string) => void;
    refreshWallpaperPreview: () => void;
    scheduleWallpaperRefresh: () => void;
    refreshSettingsAfterPreferencesReset: () => Promise<void>;
    rebindConfigForm: () => void;
    notifySaveChanged: () => void;
    requestSave: () => void;
    syncManualDirtyField: (key: string, modified: boolean, valid: boolean) => void;
    clearManualDirtyField: (key: string) => void;
}

interface SettingsMarkupHost {
    renderMarkup: (element: Element, html: TrustedHtml) => void;
}

export type { SettingsManagerCallbacks, SettingsMarkupHost, SettingsPageDependencies, SettingsRuntimeContext, SettingsPageState, SettingsRuntimeOwners };
