/* SoAI - Shared API OS endpoint contracts [frontend/assets/ts/core/api/endpoints/osEndpointContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SignalOptions } from '@core/api/requestOptions.ts';
import type { OsOperationResponse } from '@core/api/contracts/osOperationContracts.ts';
import type { OsNetworkConnectionsResponse, OsNetworkDevicesResponse, OsNetworkProfileResponse, OsNetworkStatusResponse } from '@core/api/contracts/osNetworkContracts.ts';
import type { OsStorageDeviceResponse, OsStorageDevicesResponse, OsStorageFstabResponse, OsStoragePartitionsResponse, OsStorageStatusResponse } from '@core/api/contracts/osStorageContracts.ts';
import type { OsInstalledPackagesResponse, OsRebootRequiredResponse, OsUpgradablePackagesResponse, OsUpdateHistoryResponse, OsUpdatesStatusResponse } from '@core/api/contracts/osUpdatesContracts.ts';
import type { OsCapabilitiesResponse, OsDkmsStatus, OsDriversStatus, OsLogsResponse, OsMaintenanceStatus, OsSecureBootStatus, OsSshStatus, OsStatusResponse, OsSystemdServiceStatus, OsSystemUserInfo, OsTimeSyncStatus, OsUserMappingResponse, OsUserSyncStatus } from '@core/api/contracts/osSystemContracts.ts';

interface OsDryRunPayload {
    dryRun?: boolean;
}

interface OsRollbackPayload extends OsDryRunPayload {
    rollbackMs?: number;
}

interface OsWebuiUserPayload extends OsDryRunPayload {
    webuiUserId: number;
}

interface OsSshKeysPayload extends OsWebuiUserPayload {
    publicKeys?: readonly string[];
}

interface OsNetworkConnectionModifyPayload extends OsDryRunPayload {
    ipv4Method?: 'auto' | 'manual';
    ipv4Addresses?: readonly string[];
    ipv4Gateway?: string;
    ipv4Dns?: readonly string[];
    ipv6Method?: 'auto' | 'manual';
    ipv6Addresses?: readonly string[];
    ipv6Gateway?: string;
    ipv6Dns?: readonly string[];
    autoconnect?: boolean;
}

interface OsNetworkConnectionActivatePayload extends OsRollbackPayload {
    device?: string;
}

interface OsStorageCreatePartitionPayload extends OsDryRunPayload {
    device: string;
    deviceFingerprint: string;
    start?: string;
    end?: string;
    filesystem?: string;
    partitionName?: string;
}

interface OsStorageFormatPartitionPayload extends OsDryRunPayload {
    deviceFingerprint: string;
    filesystem: string;
    label?: string;
    allowWipe?: boolean;
    recoveryRequestId?: string;
}

interface OsStorageFormatRecoveryReleasePayload {
    partitionPath: string;
}

interface OsStorageMountPayload extends OsDryRunPayload {
    mountPoint: string;
}

interface OsStorageFstabAddPayload extends OsDryRunPayload {
    uuid: string;
    mountPoint: string;
    filesystem: string;
}

interface OsDriverInstallPayload extends OsDryRunPayload {
    driverId: string;
    driverVariant?: string;
}

interface OsDriverUninstallPayload extends OsDryRunPayload {
    driverId: string;
}

interface OsUpdatesInstallPayload extends OsDryRunPayload {
    packages?: readonly string[];
    distUpgrade?: boolean;
}

interface OsMaintenanceServiceControlPayload extends OsDryRunPayload {
    action: string;
}

interface OsMaintenancePowerPayload extends OsDryRunPayload {
    delayMinutes?: number;
    message?: string;
}

type OsDryRunSignalOptions = SignalOptions & OsDryRunPayload;
type OsUpdatesCheckOptions = SignalOptions & { force?: boolean; dryRun?: boolean };
type OsUpdatesHistoryOptions = SignalOptions & { limit?: number };
type OsUpdatesPackagesOptions = SignalOptions & { filter?: string };
type OsMaintenanceLogsOptions = SignalOptions & { unit?: string; lines?: number; since?: string };
type OsOptionsEndpoint<TResponse> = (options?: SignalOptions) => Promise<TResponse>;

interface OsNetworkConnectionEndpoints {
    list: OsOptionsEndpoint<OsNetworkConnectionsResponse>;
    profile: (connectionId: string, options?: SignalOptions) => Promise<OsNetworkProfileResponse>;
    modify: (connectionId: string, payload: OsNetworkConnectionModifyPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    delete: (connectionId: string, options?: OsDryRunSignalOptions) => Promise<OsOperationResponse>;
    activate: (connectionId: string, payload: OsNetworkConnectionActivatePayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    deactivate: (connectionId: string, payload: OsRollbackPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
}

interface OsNetworkEndpoints {
    status: OsOptionsEndpoint<OsNetworkStatusResponse>;
    connections: OsNetworkConnectionEndpoints;
    devices: { list: OsOptionsEndpoint<OsNetworkDevicesResponse> };
    safeApply: {
        commit: (taskId: string, payload?: OsDryRunPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        rollback: (taskId: string, payload?: OsDryRunPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    };
}

interface OsStorageEndpoints {
    status: OsOptionsEndpoint<OsStorageStatusResponse>;
    devices: {
        list: OsOptionsEndpoint<OsStorageDevicesResponse>;
        get: (device: string, options?: SignalOptions) => Promise<OsStorageDeviceResponse>;
        partitions: (device: string, options?: SignalOptions) => Promise<OsStoragePartitionsResponse>;
    };
    partitions: {
        create: (payload: OsStorageCreatePartitionPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        format: (partition: string, payload: OsStorageFormatPartitionPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        mount: (partition: string, payload: OsStorageMountPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        unmount: (partition: string, payload?: OsDryRunPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    };
    formatRecoveries: {
        release: (requestId: string, payload: OsStorageFormatRecoveryReleasePayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    };
    fstab: {
        list: OsOptionsEndpoint<OsStorageFstabResponse>;
        add: (payload: OsStorageFstabAddPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        remove: (mountPoint: string, options?: OsDryRunSignalOptions) => Promise<OsOperationResponse>;
    };
}

interface OsEndpoints {
    capabilities: OsOptionsEndpoint<OsCapabilitiesResponse>;
    status: OsOptionsEndpoint<OsStatusResponse>;
    network: OsNetworkEndpoints;
    storage: OsStorageEndpoints;
    users: {
        status: OsOptionsEndpoint<OsUserSyncStatus>;
        mapping: OsOptionsEndpoint<OsUserMappingResponse>;
        sync: (payload: OsWebuiUserPayload, options?: SignalOptions) => Promise<OsSystemUserInfo | OsOperationResponse>;
        lock: (payload: OsWebuiUserPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        sshKeys: (payload: OsSshKeysPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    };
    ssh: {
        status: OsOptionsEndpoint<OsSshStatus>;
        disable: (payload: OsRollbackPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        enable: (payload?: OsDryRunPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        safeDisable: {
            commit: (taskId: string, payload?: OsDryRunPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
            rollback: (taskId: string, payload?: OsDryRunPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        };
    };
    drivers: {
        status: OsOptionsEndpoint<OsDriversStatus>;
        dkms: OsOptionsEndpoint<OsDkmsStatus>;
        secureBoot: OsOptionsEndpoint<OsSecureBootStatus>;
        install: (payload: OsDriverInstallPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        uninstall: (payload: OsDriverUninstallPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    };
    updates: {
        status: OsOptionsEndpoint<OsUpdatesStatusResponse>;
        upgradablePackages: OsOptionsEndpoint<OsUpgradablePackagesResponse>;
        check: (options?: OsUpdatesCheckOptions) => Promise<OsOperationResponse>;
        install: (payload: OsUpdatesInstallPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        history: (options?: OsUpdatesHistoryOptions) => Promise<OsUpdateHistoryResponse>;
        packages: (options?: OsUpdatesPackagesOptions) => Promise<OsInstalledPackagesResponse>;
        rebootRequired: OsOptionsEndpoint<OsRebootRequiredResponse>;
    };
    maintenance: {
        status: OsOptionsEndpoint<OsMaintenanceStatus>;
        services: {
            get: (name: string, options?: SignalOptions) => Promise<OsSystemdServiceStatus>;
            control: (name: string, payload: OsMaintenanceServiceControlPayload, options?: SignalOptions) => Promise<OsSystemdServiceStatus | OsOperationResponse>;
        };
        logs: (options?: OsMaintenanceLogsOptions) => Promise<OsLogsResponse>;
        time: OsOptionsEndpoint<OsTimeSyncStatus>;
        restart: (payload: OsMaintenancePowerPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
        shutdown: (payload: OsMaintenancePowerPayload, options?: SignalOptions) => Promise<OsOperationResponse>;
    };
}

export type { OsDriverInstallPayload, OsDriverUninstallPayload, OsDryRunPayload, OsDryRunSignalOptions, OsEndpoints, OsMaintenanceLogsOptions, OsMaintenancePowerPayload, OsMaintenanceServiceControlPayload, OsNetworkConnectionActivatePayload, OsNetworkConnectionModifyPayload, OsNetworkEndpoints, OsRollbackPayload, OsSshKeysPayload, OsStorageCreatePartitionPayload, OsStorageEndpoints, OsStorageFormatPartitionPayload, OsStorageFormatRecoveryReleasePayload, OsStorageFstabAddPayload, OsStorageMountPayload, OsUpdatesCheckOptions, OsUpdatesHistoryOptions, OsUpdatesInstallPayload, OsUpdatesPackagesOptions, OsWebuiUserPayload };
