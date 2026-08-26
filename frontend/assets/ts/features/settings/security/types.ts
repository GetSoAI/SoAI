/* SoAI - Settings security audit types [frontend/assets/ts/features/settings/security/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SecurityHardeningAudit } from '@core/api/contracts/systemContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { SettingsCapabilityAvailability } from '@features/settings/capabilityAvailability.ts';

interface SecurityManagerHost extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    filterSettings: () => void;
    hasSearchQuery: () => boolean;
    rebindConfigForm: () => void;
    openUsersTab: () => void;
    getCoreConfig: () => JsonObject;
    getSecurityAudit: () => SecurityHardeningAudit | null;
    setSecurityAudit: (audit: SecurityHardeningAudit) => void;
    getSecurityAvailability: () => SettingsCapabilityAvailability;
    setSecurityAvailability: (availability: SettingsCapabilityAvailability) => void;
    loadSecurityAudit: (options?: RequestOptions) => Promise<SecurityHardeningAudit>;
}

interface SecurityManagerDependencies {
    host: SecurityManagerHost;
}

export type { SecurityManagerDependencies, SecurityManagerHost };
