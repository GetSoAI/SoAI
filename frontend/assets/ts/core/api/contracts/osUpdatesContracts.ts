/* SoAI - Frontend OS updates response contracts [frontend/assets/ts/core/api/contracts/osUpdatesContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';

interface OsUpgradablePackage {
    name: string;
    currentVersion: string | null;
    newVersion: string | null;
    isSecurity: boolean;
    downloadSize: number;
}
interface OsUpdatesStatusResponse {
    availableUpdatesCount: number;
    securityUpdatesCount: number;
    lastCheckAtMs: number | null;
    rebootRequired: boolean;
    timestampMs: number;
}
interface OsUpgradablePackagesResponse {
    checkedAtMs: number | null;
    availableUpdatesCount: number;
    securityUpdatesCount: number;
    packages: OsUpgradablePackage[];
}
interface OsInstalledPackage {
    name: string;
    version: string;
    architecture: string | null;
}
interface OsInstalledPackagesResponse {
    packages: OsInstalledPackage[];
}
interface OsUpdateHistoryEntry {
    startDate: string | null;
    endDate: string | null;
    commandline: string | null;
    installed: string[];
    upgraded: string[];
    removed: string[];
}
interface OsUpdateHistoryResponse {
    entries: OsUpdateHistoryEntry[];
}
interface OsRebootRequiredResponse {
    rebootRequired: boolean;
}

const nullableString = (value: ApiResponsePayload, label: string): string | null => (value === null ? null : readRequiredStringValue(value, label));
const nullableNumber = (value: ApiResponsePayload, label: string): number | null => (value === null ? null : readRequiredFiniteNumberValue(value, label));
const array = (value: ApiResponsePayload, label: string): ApiResponsePayload[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return [...value];
};
const strings = (value: ApiResponsePayload, label: string): string[] => array(value, label).map((entry, index) => readRequiredStringValue(entry, `${label}[${String(index)}]`));
const decodePackage = (value: ApiResponsePayload, label: string): OsUpgradablePackage => {
    const record = requireRecord(value, label);
    return { name: readRequiredStringValue(record['name'], `${label}.name`), currentVersion: nullableString(record['current_version'] ?? null, `${label}.current_version`), newVersion: nullableString(record['new_version'] ?? null, `${label}.new_version`), isSecurity: readRequiredBooleanValue(record['is_security'], `${label}.is_security`), downloadSize: readRequiredFiniteNumberValue(record['download_size'], `${label}.download_size`) };
};
const decodeOsUpdatesStatus = (value: ApiResponsePayload): OsUpdatesStatusResponse => {
    const record = requireRecord(value, 'OS updates status');
    return { availableUpdatesCount: readRequiredFiniteNumberValue(record['available_updates_count'], 'OS updates status.available_updates_count'), securityUpdatesCount: readRequiredFiniteNumberValue(record['security_updates_count'], 'OS updates status.security_updates_count'), lastCheckAtMs: nullableNumber(record['last_check_at_ms'] ?? null, 'OS updates status.last_check_at_ms'), rebootRequired: readRequiredBooleanValue(record['reboot_required'], 'OS updates status.reboot_required'), timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], 'OS updates status.timestamp_ms') };
};
const decodeOsUpgradablePackages = (value: ApiResponsePayload): OsUpgradablePackagesResponse => {
    const record = requireRecord(value, 'OS upgradable packages');
    return { checkedAtMs: nullableNumber(record['checked_at_ms'] ?? null, 'OS upgradable packages.checked_at_ms'), availableUpdatesCount: readRequiredFiniteNumberValue(record['available_updates_count'], 'OS upgradable packages.available_updates_count'), securityUpdatesCount: readRequiredFiniteNumberValue(record['security_updates_count'], 'OS upgradable packages.security_updates_count'), packages: array(record['packages'], 'OS upgradable packages.packages').map((entry, index) => decodePackage(entry, `OS upgradable packages.packages[${String(index)}]`)) };
};
const decodeOsInstalledPackages = (value: ApiResponsePayload): OsInstalledPackagesResponse => {
    const record = requireRecord(value, 'OS installed packages');
    return {
        packages: array(record['packages'], 'OS installed packages.packages').map((entry, index) => {
            const packageRecord = requireRecord(entry, `OS installed packages.packages[${String(index)}]`);
            return { name: readRequiredStringValue(packageRecord['name'], 'OS installed package.name'), version: readRequiredStringValue(packageRecord['version'], 'OS installed package.version'), architecture: nullableString(packageRecord['architecture'] ?? null, 'OS installed package.architecture') };
        })
    };
};
const decodeOsUpdateHistory = (value: ApiResponsePayload): OsUpdateHistoryResponse => {
    const record = requireRecord(value, 'OS update history');
    return {
        entries: array(record['entries'], 'OS update history.entries').map((entry, index) => {
            const history = requireRecord(entry, `OS update history.entries[${String(index)}]`);
            return { startDate: nullableString(history['start_date'] ?? null, 'OS update history.start_date'), endDate: nullableString(history['end_date'] ?? null, 'OS update history.end_date'), commandline: nullableString(history['commandline'] ?? null, 'OS update history.commandline'), installed: strings(history['installed'], 'OS update history.installed'), upgraded: strings(history['upgraded'], 'OS update history.upgraded'), removed: strings(history['removed'], 'OS update history.removed') };
        })
    };
};
const decodeOsRebootRequired = (value: ApiResponsePayload): OsRebootRequiredResponse => {
    const record = requireRecord(value, 'OS reboot required');
    return { rebootRequired: readRequiredBooleanValue(record['reboot_required'], 'OS reboot required.reboot_required') };
};

export { decodeOsInstalledPackages, decodeOsRebootRequired, decodeOsUpdateHistory, decodeOsUpdatesStatus, decodeOsUpgradablePackages };
export type { OsInstalledPackage, OsInstalledPackagesResponse, OsRebootRequiredResponse, OsUpgradablePackage, OsUpgradablePackagesResponse, OsUpdateHistoryEntry, OsUpdateHistoryResponse, OsUpdatesStatusResponse };
