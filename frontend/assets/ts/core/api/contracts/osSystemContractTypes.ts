/* SoAI - Frontend OS system contract types [frontend/assets/ts/core/api/contracts/osSystemContractTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OsNetworkStatusResponse } from '@core/api/contracts/osNetworkContracts.ts';
import type { OsSystemStorageStatusResponse } from '@core/api/contracts/osStorageContracts.ts';
import type { OsUpdatesStatusResponse } from '@core/api/contracts/osUpdatesContracts.ts';

interface OsCapabilities {
    systemctlAvailable: boolean;
    systemdActive: boolean;
    soaiServiceInstalled: boolean;
    soaiServiceEnabled: boolean;
    soaiServiceConflict: boolean;
    networkManager: boolean;
    aptAvailable: boolean;
    dkmsAvailable: boolean;
    secureBootEnabled: boolean;
    isRoot: boolean;
    sudoAvailable: boolean;
    debianVersion: string | null;
}
interface OsCapabilitiesResponse {
    enabled: boolean;
    capabilities: OsCapabilities;
}
interface OsUserSyncStatus {
    enabled: boolean;
    timestampMs: number;
}
interface OsSystemUserInfo {
    webuiUserId: number;
    linuxUsername: string;
    exists: boolean;
    uid: number | null;
    gid: number | null;
    homeDir: string | null;
    shell: string | null;
    locked: boolean | null;
    groups: string[];
}
interface OsUserMappingResponse {
    mapping: Record<string, OsSystemUserInfo>;
}
interface OsSshStatus {
    serviceName: string;
    active: boolean;
    enabled: boolean;
    activeState: string | null;
    enabledState: string | null;
    timestampMs: number;
}
interface OsDkmsModule {
    name: string;
    version: string;
    kernelVersion: string;
    status: string;
    arch: string;
}
interface OsDkmsStatus {
    modules: OsDkmsModule[];
}
interface OsSecureBootStatus {
    enabled: boolean;
    setupMode: boolean;
    mokKeysPresent: boolean;
    mokEnrolled: boolean;
}
interface OsDriverPackage {
    packageName: string;
    installedVersion: string | null;
    candidateVersion: string | null;
    preferredSuite: string | null;
    installed: boolean;
}
interface OsDriverRuntimeTool {
    toolName: string;
    executable: string;
    available: boolean;
    version: string | null;
    unsupportedReason: string | null;
}
interface OsDriverVariant {
    variantId: string;
    label: string;
}
interface OsDriverStatus {
    driverId: string;
    vendor: string;
    displayName: string;
    detected: boolean;
    installed: boolean;
    kernelActive: boolean;
    runtimeReady: boolean;
    ready: boolean;
    installable: boolean;
    uninstallable: boolean;
    variantId: string | null;
    availableVariants: OsDriverVariant[];
    kernelModules: string[];
    packages: OsDriverPackage[];
    runtimeTools: OsDriverRuntimeTool[];
    warnings: string[];
    rebootRequired: boolean;
}
interface OsDriversStatus {
    drivers: OsDriverStatus[];
    dkmsModules: OsDkmsModule[];
    secureBootStatus: OsSecureBootStatus;
}
interface OsMaintenanceStatus {
    timeSyncActive: boolean;
    timeSyncServer: string | null;
    systemUptimeMs: number;
    loadAverage: [number, number, number];
    timestampMs: number;
}
interface OsTimeSyncStatus {
    active: boolean;
    synchronized: boolean;
    server: string | null;
    ntpService: string;
    systemTime: string | null;
    rtcTime: string | null;
    timezone: string | null;
    timestampMs: number;
}
interface OsSystemdServiceStatus {
    name: string;
    description: string | null;
    loadState: string | null;
    activeState: string | null;
    subState: string | null;
    unitFileState: string | null;
    mainPid: number | null;
    memoryCurrent: number | null;
}
interface OsLogEntry {
    timestampMs: number;
    priority: number;
    unit: string | null;
    message: string;
    hostname: string | null;
}
interface OsLogsResponse {
    entries: OsLogEntry[];
}
interface OsStatusResponse {
    enabled: boolean;
    mode: string;
    capabilities: OsCapabilities;
    drivers: OsDriversStatus;
    network: OsNetworkStatusResponse;
    storage: OsSystemStorageStatusResponse;
    updates: OsUpdatesStatusResponse;
    users: OsUserSyncStatus;
    ssh: OsSshStatus;
    maintenance: OsMaintenanceStatus;
    timeSync: OsTimeSyncStatus;
    timestampMs: number;
}

export type { OsCapabilities, OsCapabilitiesResponse, OsDkmsModule, OsDkmsStatus, OsDriverPackage, OsDriverRuntimeTool, OsDriversStatus, OsDriverStatus, OsDriverVariant, OsLogEntry, OsLogsResponse, OsMaintenanceStatus, OsSecureBootStatus, OsSshStatus, OsStatusResponse, OsSystemdServiceStatus, OsSystemUserInfo, OsTimeSyncStatus, OsUserMappingResponse, OsUserSyncStatus };
