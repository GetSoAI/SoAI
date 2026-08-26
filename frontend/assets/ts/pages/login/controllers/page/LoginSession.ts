/* SoAI - Login loading, cooldown, DOM, authentication, and task ownership [frontend/assets/ts/pages/login/controllers/page/LoginSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AuthService } from '@pages/login/types.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { StateManager } from '@core/state/StateManager.ts';
import type { StorageService } from '@core/storage/StorageService.ts';

interface LoginSessionDependencies {
    auth: AuthService | null;
    streaming: PageStreaming;
    pageElements: PageUi;
    pageDom: PageDom;
    pageResources: PageResources;
    stateManager: StateManager | null;
    storage: StorageService;
}

class LoginSession {
    readonly auth: AuthService | null;
    readonly streaming: PageStreaming;
    readonly pageElements: PageUi;
    readonly pageDom: PageDom;
    readonly pageResources: PageResources;
    readonly stateManager: StateManager | null;
    readonly storage: StorageService;
    isLoading = false;

    constructor(dependencies: LoginSessionDependencies) {
        this.auth = dependencies.auth;
        this.streaming = dependencies.streaming;
        this.pageElements = dependencies.pageElements;
        this.pageDom = dependencies.pageDom;
        this.pageResources = dependencies.pageResources;
        this.stateManager = dependencies.stateManager;
        this.storage = dependencies.storage;
    }
}

export { LoginSession };
export type { LoginSessionDependencies };
