/* SoAI - Frontend OS system response contracts [frontend/assets/ts/core/api/contracts/osSystemContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';
import { decodeOsNetworkStatus } from '@core/api/contracts/osNetworkContracts.ts';
import { decodeOsSystemStorageStatus } from '@core/api/contracts/osStorageContracts.ts';
import { decodeOsUpdatesStatus } from '@core/api/contracts/osUpdatesContracts.ts';
import { decodeOsOperationResponse, type OsOperationResponse } from '@core/api/contracts/osOperationContracts.ts';
import type { OsCapabilities, OsCapabilitiesResponse, OsDkmsModule, OsDkmsStatus, OsDriverPackage, OsDriverRuntimeTool, OsDriversStatus, OsDriverStatus, OsDriverVariant, OsLogEntry, OsLogsResponse, OsMaintenanceStatus, OsSecureBootStatus, OsSshStatus, OsStatusResponse, OsSystemdServiceStatus, OsSystemUserInfo, OsTimeSyncStatus, OsUserMappingResponse, OsUserSyncStatus } from '@core/api/contracts/osSystemContractTypes.ts';

const nullableString = (value: ApiResponsePayload, label: string): string | null => (value === null ? null : readRequiredStringValue(value, label));
const nullableNumber = (value: ApiResponsePayload, label: string): number | null => (value === null ? null : readRequiredFiniteNumberValue(value, label));
const nullableBoolean = (value: ApiResponsePayload, label: string): boolean | null => (value === null ? null : readRequiredBooleanValue(value, label));
const array = (value: ApiResponsePayload, label: string): ApiResponsePayload[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return [...value];
};
const strings = (value: ApiResponsePayload, label: string): string[] => array(value, label).map((entry, index) => readRequiredStringValue(entry, `${label}[${String(index)}]`));
const decodeCapabilities = (value: ApiResponsePayload, label: string): OsCapabilities => {
    const record = requireRecord(value, label);
    return {
        systemctlAvailable: readRequiredBooleanValue(record['systemctl_available'], `${label}.systemctl_available`),
        systemdActive: readRequiredBooleanValue(record['systemd_active'], `${label}.systemd_active`),
        soaiServiceInstalled: readRequiredBooleanValue(record['soai_service_installed'], `${label}.soai_service_installed`),
        soaiServiceEnabled: readRequiredBooleanValue(record['soai_service_enabled'], `${label}.soai_service_enabled`),
        soaiServiceConflict: readRequiredBooleanValue(record['soai_service_conflict'], `${label}.soai_service_conflict`),
        networkManager: readRequiredBooleanValue(record['network_manager'], `${label}.network_manager`),
        aptAvailable: readRequiredBooleanValue(record['apt_available'], `${label}.apt_available`),
        dkmsAvailable: readRequiredBooleanValue(record['dkms_available'], `${label}.dkms_available`),
        secureBootEnabled: readRequiredBooleanValue(record['secure_boot_enabled'], `${label}.secure_boot_enabled`),
        isRoot: readRequiredBooleanValue(record['is_root'], `${label}.is_root`),
        sudoAvailable: readRequiredBooleanValue(record['sudo_available'], `${label}.sudo_available`),
        debianVersion: nullableString(record['debian_version'] ?? null, `${label}.debian_version`)
    };
};
const decodeDkmsModule = (value: ApiResponsePayload, label: string): OsDkmsModule => {
    const record = requireRecord(value, label);
    return { name: readRequiredStringValue(record['name'], `${label}.name`), version: readRequiredStringValue(record['version'], `${label}.version`), kernelVersion: readRequiredStringValue(record['kernel_version'], `${label}.kernel_version`), status: readRequiredStringValue(record['status'], `${label}.status`), arch: readRequiredStringValue(record['arch'], `${label}.arch`) };
};
const decodeSecureBoot = (value: ApiResponsePayload, label: string): OsSecureBootStatus => {
    const record = requireRecord(value, label);
    return { enabled: readRequiredBooleanValue(record['enabled'], `${label}.enabled`), setupMode: readRequiredBooleanValue(record['setup_mode'], `${label}.setup_mode`), mokKeysPresent: readRequiredBooleanValue(record['mok_keys_present'], `${label}.mok_keys_present`), mokEnrolled: readRequiredBooleanValue(record['mok_enrolled'], `${label}.mok_enrolled`) };
};
const decodeDriver = (value: ApiResponsePayload, label: string): OsDriverStatus => {
    const record = requireRecord(value, label);
    return {
        driverId: readRequiredStringValue(record['driver_id'], `${label}.driver_id`),
        vendor: readRequiredStringValue(record['vendor'], `${label}.vendor`),
        displayName: readRequiredStringValue(record['display_name'], `${label}.display_name`),
        detected: readRequiredBooleanValue(record['detected'], `${label}.detected`),
        installed: readRequiredBooleanValue(record['installed'], `${label}.installed`),
        kernelActive: readRequiredBooleanValue(record['kernel_active'], `${label}.kernel_active`),
        runtimeReady: readRequiredBooleanValue(record['runtime_ready'], `${label}.runtime_ready`),
        ready: readRequiredBooleanValue(record['ready'], `${label}.ready`),
        installable: readRequiredBooleanValue(record['installable'], `${label}.installable`),
        uninstallable: readRequiredBooleanValue(record['uninstallable'], `${label}.uninstallable`),
        variantId: nullableString(record['variant_id'] ?? null, `${label}.variant_id`),
        availableVariants: array(record['available_variants'], `${label}.available_variants`).map((entry, index) => {
            const variant = requireRecord(entry, `${label}.available_variants[${String(index)}]`);
            return { variantId: readRequiredStringValue(variant['variant_id'], `${label}.variant_id`), label: readRequiredStringValue(variant['label'], `${label}.label`) };
        }),
        kernelModules: strings(record['kernel_modules'], `${label}.kernel_modules`),
        packages: array(record['packages'], `${label}.packages`).map((entry, index) => {
            const pkg = requireRecord(entry, `${label}.packages[${String(index)}]`);
            return { packageName: readRequiredStringValue(pkg['package_name'], `${label}.package_name`), installedVersion: nullableString(pkg['installed_version'] ?? null, `${label}.installed_version`), candidateVersion: nullableString(pkg['candidate_version'] ?? null, `${label}.candidate_version`), preferredSuite: nullableString(pkg['preferred_suite'] ?? null, `${label}.preferred_suite`), installed: readRequiredBooleanValue(pkg['installed'], `${label}.installed`) };
        }),
        runtimeTools: array(record['runtime_tools'], `${label}.runtime_tools`).map((entry, index) => {
            const tool = requireRecord(entry, `${label}.runtime_tools[${String(index)}]`);
            return { toolName: readRequiredStringValue(tool['tool_name'], `${label}.tool_name`), executable: readRequiredStringValue(tool['executable'], `${label}.executable`), available: readRequiredBooleanValue(tool['available'], `${label}.available`), version: nullableString(tool['version'] ?? null, `${label}.version`), unsupportedReason: nullableString(tool['unsupported_reason'] ?? null, `${label}.unsupported_reason`) };
        }),
        warnings: strings(record['warnings'], `${label}.warnings`),
        rebootRequired: readRequiredBooleanValue(record['reboot_required'], `${label}.reboot_required`)
    };
};
const decodeDrivers = (value: ApiResponsePayload, label: string): OsDriversStatus => {
    const record = requireRecord(value, label);
    return { drivers: array(record['drivers'], `${label}.drivers`).map((entry, index) => decodeDriver(entry, `${label}.drivers[${String(index)}]`)), dkmsModules: array(record['dkms_modules'], `${label}.dkms_modules`).map((entry, index) => decodeDkmsModule(entry, `${label}.dkms_modules[${String(index)}]`)), secureBootStatus: decodeSecureBoot(record['secure_boot_status'], `${label}.secure_boot_status`) };
};
const decodeUserSyncStatus = (value: ApiResponsePayload, label: string): OsUserSyncStatus => {
    const record = requireRecord(value, label);
    return { enabled: readRequiredBooleanValue(record['enabled'], `${label}.enabled`), timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], `${label}.timestamp_ms`) };
};
const decodeSystemUser = (value: ApiResponsePayload, label: string): OsSystemUserInfo => {
    const record = requireRecord(value, label);
    return { webuiUserId: readRequiredFiniteNumberValue(record['webui_user_id'], `${label}.webui_user_id`), linuxUsername: readRequiredStringValue(record['linux_username'], `${label}.linux_username`), exists: readRequiredBooleanValue(record['exists'], `${label}.exists`), uid: nullableNumber(record['uid'] ?? null, `${label}.uid`), gid: nullableNumber(record['gid'] ?? null, `${label}.gid`), homeDir: nullableString(record['home_dir'] ?? null, `${label}.home_dir`), shell: nullableString(record['shell'] ?? null, `${label}.shell`), locked: nullableBoolean(record['locked'] ?? null, `${label}.locked`), groups: strings(record['groups'], `${label}.groups`) };
};
const decodeSshStatus = (value: ApiResponsePayload, label: string): OsSshStatus => {
    const record = requireRecord(value, label);
    return { serviceName: readRequiredStringValue(record['service_name'], `${label}.service_name`), active: readRequiredBooleanValue(record['active'], `${label}.active`), enabled: readRequiredBooleanValue(record['enabled'], `${label}.enabled`), activeState: nullableString(record['active_state'] ?? null, `${label}.active_state`), enabledState: nullableString(record['enabled_state'] ?? null, `${label}.enabled_state`), timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], `${label}.timestamp_ms`) };
};
const decodeMaintenance = (value: ApiResponsePayload, label: string): OsMaintenanceStatus => {
    const record = requireRecord(value, label);
    const load = array(record['load_average'], `${label}.load_average`);
    if (load.length !== 3) throw new TypeError(`${label}.load_average must contain three values`);
    return { timeSyncActive: readRequiredBooleanValue(record['time_sync_active'], `${label}.time_sync_active`), timeSyncServer: nullableString(record['time_sync_server'] ?? null, `${label}.time_sync_server`), systemUptimeMs: readRequiredFiniteNumberValue(record['system_uptime_ms'], `${label}.system_uptime_ms`), loadAverage: [readRequiredFiniteNumberValue(load[0], `${label}.load_average[0]`), readRequiredFiniteNumberValue(load[1], `${label}.load_average[1]`), readRequiredFiniteNumberValue(load[2], `${label}.load_average[2]`)], timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], `${label}.timestamp_ms`) };
};
const decodeTimeSync = (value: ApiResponsePayload, label: string): OsTimeSyncStatus => {
    const record = requireRecord(value, label);
    return { active: readRequiredBooleanValue(record['active'], `${label}.active`), synchronized: readRequiredBooleanValue(record['synchronized'], `${label}.synchronized`), server: nullableString(record['server'] ?? null, `${label}.server`), ntpService: readRequiredStringValue(record['ntp_service'], `${label}.ntp_service`), systemTime: nullableString(record['system_time'] ?? null, `${label}.system_time`), rtcTime: nullableString(record['rtc_time'] ?? null, `${label}.rtc_time`), timezone: nullableString(record['timezone'] ?? null, `${label}.timezone`), timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], `${label}.timestamp_ms`) };
};
const decodeOsCapabilities = (value: ApiResponsePayload): OsCapabilitiesResponse => {
    const record = requireRecord(value, 'OS capabilities');
    return { enabled: readRequiredBooleanValue(record['enabled'], 'OS capabilities.enabled'), capabilities: decodeCapabilities(record['capabilities'], 'OS capabilities.capabilities') };
};
const decodeOsUserMapping = (value: ApiResponsePayload): OsUserMappingResponse => {
    const record = requireRecord(value, 'OS user mapping');
    const mapping = requireRecord(record['mapping'], 'OS user mapping.mapping');
    return { mapping: Object.fromEntries(Object.entries(mapping).map(([userId, entry]) => [userId, decodeSystemUser(entry, `OS user mapping.mapping.${userId}`)])) };
};
const decodeOsSystemUser = (value: ApiResponsePayload): OsSystemUserInfo => decodeSystemUser(value, 'OS system user');
const decodeOsUserSyncResponse = (value: ApiResponsePayload): OsSystemUserInfo | OsOperationResponse => {
    const record = requireRecord(value, 'OS user sync');
    return record['dry_run'] === true ? decodeOsOperationResponse(value, 'OS user sync') : decodeSystemUser(value, 'OS user sync');
};
const decodeOsUserStatus = (value: ApiResponsePayload): OsUserSyncStatus => decodeUserSyncStatus(value, 'OS user status');
const decodeOsSshStatus = (value: ApiResponsePayload): OsSshStatus => decodeSshStatus(value, 'OS SSH status');
const decodeOsDriversStatus = (value: ApiResponsePayload): OsDriversStatus => decodeDrivers(value, 'OS drivers status');
const decodeOsDkmsStatus = (value: ApiResponsePayload): OsDkmsStatus => {
    const record = requireRecord(value, 'OS DKMS status');
    return { modules: array(record['modules'], 'OS DKMS status.modules').map((entry, index) => decodeDkmsModule(entry, `OS DKMS status.modules[${String(index)}]`)) };
};
const decodeOsSecureBootStatus = (value: ApiResponsePayload): OsSecureBootStatus => decodeSecureBoot(value, 'OS secure boot status');
const decodeOsMaintenanceStatus = (value: ApiResponsePayload): OsMaintenanceStatus => decodeMaintenance(value, 'OS maintenance status');
const decodeOsTimeSyncStatus = (value: ApiResponsePayload): OsTimeSyncStatus => decodeTimeSync(value, 'OS time sync status');
const decodeOsServiceStatus = (value: ApiResponsePayload): OsSystemdServiceStatus => {
    const record = requireRecord(value, 'OS service status');
    return { name: readRequiredStringValue(record['name'], 'OS service status.name'), description: nullableString(record['description'] ?? null, 'OS service status.description'), loadState: nullableString(record['load_state'] ?? null, 'OS service status.load_state'), activeState: nullableString(record['active_state'] ?? null, 'OS service status.active_state'), subState: nullableString(record['sub_state'] ?? null, 'OS service status.sub_state'), unitFileState: nullableString(record['unit_file_state'] ?? null, 'OS service status.unit_file_state'), mainPid: nullableNumber(record['main_pid'] ?? null, 'OS service status.main_pid'), memoryCurrent: nullableNumber(record['memory_current'] ?? null, 'OS service status.memory_current') };
};
const decodeOsServiceControl = (value: ApiResponsePayload): OsSystemdServiceStatus | OsOperationResponse => {
    const record = requireRecord(value, 'OS service control');
    return record['dry_run'] === true ? decodeOsOperationResponse(value, 'OS service control') : decodeOsServiceStatus(value);
};
const decodeOsLogs = (value: ApiResponsePayload): OsLogsResponse => {
    const record = requireRecord(value, 'OS logs');
    return {
        entries: array(record['entries'], 'OS logs.entries').map((entry, index) => {
            const log = requireRecord(entry, `OS logs.entries[${String(index)}]`);
            return { timestampMs: readRequiredFiniteNumberValue(log['timestamp_ms'], 'OS log.timestamp_ms'), priority: readRequiredFiniteNumberValue(log['priority'], 'OS log.priority'), unit: nullableString(log['unit'] ?? null, 'OS log.unit'), message: readRequiredStringValue(log['message'], 'OS log.message'), hostname: nullableString(log['hostname'] ?? null, 'OS log.hostname') };
        })
    };
};
const decodeOsStatus = (value: ApiResponsePayload): OsStatusResponse => {
    const record = requireRecord(value, 'OS status');
    return { enabled: readRequiredBooleanValue(record['enabled'], 'OS status.enabled'), mode: readRequiredStringValue(record['mode'], 'OS status.mode'), capabilities: decodeCapabilities(record['capabilities'], 'OS status.capabilities'), drivers: decodeDrivers(record['drivers'], 'OS status.drivers'), network: decodeOsNetworkStatus(record['network']), storage: decodeOsSystemStorageStatus(record['storage']), updates: decodeOsUpdatesStatus(record['updates']), users: decodeUserSyncStatus(record['users'], 'OS status.users'), ssh: decodeSshStatus(record['ssh'], 'OS status.ssh'), maintenance: decodeMaintenance(record['maintenance'], 'OS status.maintenance'), timeSync: decodeTimeSync(record['time_sync'], 'OS status.time_sync'), timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], 'OS status.timestamp_ms') };
};

export { decodeOsCapabilities, decodeOsDkmsStatus, decodeOsDriversStatus, decodeOsLogs, decodeOsMaintenanceStatus, decodeOsSecureBootStatus, decodeOsServiceControl, decodeOsServiceStatus, decodeOsSshStatus, decodeOsStatus, decodeOsSystemUser, decodeOsTimeSyncStatus, decodeOsUserMapping, decodeOsUserStatus, decodeOsUserSyncResponse };
export type { OsCapabilities, OsCapabilitiesResponse, OsDkmsModule, OsDkmsStatus, OsDriverPackage, OsDriverRuntimeTool, OsDriversStatus, OsDriverStatus, OsDriverVariant, OsLogEntry, OsLogsResponse, OsMaintenanceStatus, OsSecureBootStatus, OsSshStatus, OsStatusResponse, OsSystemdServiceStatus, OsSystemUserInfo, OsTimeSyncStatus, OsUserMappingResponse, OsUserSyncStatus };
