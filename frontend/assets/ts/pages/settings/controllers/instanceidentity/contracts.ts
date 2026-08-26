/* SoAI - Settings instance identity contracts [frontend/assets/ts/pages/settings/controllers/instanceidentity/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';

interface InstanceIdentityManagerHost extends PageDomOwnerHost, PageResourcesOwnerHost {
    updateInstanceName: (instanceName: string | null) => Promise<string | null>;
    notifySaveChanged: () => void;
    syncManualDirtyField: (key: string, modified: boolean, valid: boolean) => void;
    clearManualDirtyField: (key: string) => void;
}

interface InstanceIdentityManagerDependencies {
    host: InstanceIdentityManagerHost;
    instanceId: string;
    instanceName: string | null;
}

export type { InstanceIdentityManagerDependencies, InstanceIdentityManagerHost };
