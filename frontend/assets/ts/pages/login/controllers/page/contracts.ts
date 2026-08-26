/* SoAI - Login page control layer boundary contracts [frontend/assets/ts/pages/login/controllers/page/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SetButtonLoadingOptions } from '@core/state/UIStateManager.ts';
import type { AuthService } from '@pages/login/types.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';

interface LoginPageStorageContract {
    getSession?: () => import('@core/types/jsonValues.ts').JsonValue;
}

interface LoginPageStateManagerContract {
    setButtonLoading: (button: HTMLButtonElement, loading: boolean, options?: SetButtonLoadingOptions) => void;
}

interface LoginPageHost extends PageStreamingOwnerHost, PageUiOwnerHost, PageDomOwnerHost, PageResourcesOwnerHost {
    auth: AuthService | null;
    storage: LoginPageStorageContract;
    stateManager: LoginPageStateManagerContract | null;
    isLoading: boolean;
}

export type { LoginPageHost, LoginPageStateManagerContract, LoginPageStorageContract };
