/* SoAI - Shared routing base contracts [frontend/assets/ts/core/routing/pages/pagetypes/base/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageContext } from '@core/pagecontext/public.ts';
import type { ApiClient } from '@core/api/service.ts';
import type { AuthManager } from '@core/auth/public.ts';
import type { dom } from '@core/dom/dom.ts';
import type { loadingState } from '@core/loadingState.ts';
import type { LanguageService } from '@core/routing/pages/pagetypes/base/uiContracts.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { StateManager } from '@core/state/StateManager.ts';
import type { StorageService } from '@core/storage/StorageService.ts';

export interface BasePageDependencies {
    api: ApiClient;
    auth: AuthManager;
    dom: typeof dom;
    languageService: LanguageService;
    loadingState: typeof loadingState;
    router: Router;
    stateManager: StateManager;
    storage: StorageService;
}

export interface BasePageConstructorOptions {
    dependencies: BasePageDependencies;
    pageContext?: PageContext | null;
}
