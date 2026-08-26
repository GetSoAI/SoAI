/* SoAI - Settings page acl manager support [frontend/assets/ts/pages/settings/controllers/AclManagerSupport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AclPolicyOverrides, AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';
import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import type { SanitizerInput } from '@core/pagecontext/contracts.ts';
import type { DomEventHost, DomMutationHost, DomQueryHost, ExecutionHost, NotificationHost, SearchHost } from '@core/ui/controllerHosts.ts';
import type { SettingsCapabilityAvailability } from '@features/settings/public.ts';

interface AclManagerDependencies {
    host: AclManagerHost;
    availability: AclManagerAvailabilityPort;
}

interface AclManagerAvailabilityPort {
    get: () => SettingsCapabilityAvailability;
    set: (availability: SettingsCapabilityAvailability) => void;
}

interface AclManagerApiHost {
    isAdmin: () => boolean;
    getPolicy: () => Promise<AclPolicyResponse>;
    updatePolicy: (payload: AclPolicyOverrides) => Promise<AclPolicyResponse>;
    sanitizeAttribute: (value: SanitizerInput) => string;
}

interface AclManagerDomHost extends DomQueryHost, DomEventHost, DomMutationHost {
    updateProperty: (element: Element, property: string, value: DomPropertyValue) => void;
    updatePreferenceToggleLabel: (element: Element, checked?: boolean) => void;
}

type AclManagerExecutionHost = ExecutionHost;

interface AclManagerSaveHost {
    notifySaveChanged: () => void;
    syncManualDirtyField: (key: string, modified: boolean, valid: boolean) => void;
    clearManualDirtyField: (key: string) => void;
}

interface AclManagerPolicyStatePort {
    getAclPolicy: () => AclPolicyResponse | null;
    setAclPolicy: (policy: AclPolicyResponse) => void;
}

interface AclManagerHost extends AclManagerApiHost, AclManagerDomHost, AclManagerExecutionHost, NotificationHost, SearchHost, AclManagerPolicyStatePort, AclManagerSaveHost {}

export type { AclManagerAvailabilityPort, AclManagerDependencies, AclManagerApiHost, AclManagerDomHost, AclManagerExecutionHost, AclManagerPolicyStatePort, AclManagerSaveHost, AclManagerHost };
