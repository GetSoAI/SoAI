/* SoAI - Frontend OS network response contracts [frontend/assets/ts/core/api/contracts/osNetworkContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';

interface OsNetworkDevice {
    device: string;
    deviceType: string | null;
    state: string | null;
    connection: string | null;
    ipv4Addresses: string[];
    ipv4Gateway: string | null;
    ipv4Dns: string[];
    ipv6Addresses: string[];
    ipv6Gateway: string | null;
    ipv6Dns: string[];
}
interface OsNetworkConnection {
    connectionId: string;
    name: string;
    connectionType: string;
    device: string | null;
    state: string | null;
    active: boolean;
    profileEditable: boolean;
}
interface OsNetworkConnectionProfile {
    connectionId: string;
    name: string;
    connectionType: string;
    autoconnect: boolean;
    ipv4Method: 'auto' | 'manual';
    ipv4Addresses: string[];
    ipv4Gateway: string;
    ipv4Dns: string[];
    ipv6Method: 'auto' | 'manual';
    ipv6Addresses: string[];
    ipv6Gateway: string;
    ipv6Dns: string[];
}
interface OsNetworkStatusResponse {
    timestampMs: number;
    devices: OsNetworkDevice[];
    connections: OsNetworkConnection[];
}
interface OsNetworkConnectionsResponse {
    connections: OsNetworkConnection[];
}
interface OsNetworkDevicesResponse {
    devices: OsNetworkDevice[];
}
interface OsNetworkProfileResponse {
    profile: OsNetworkConnectionProfile;
}

const nullableString = (value: ApiResponsePayload, label: string): string | null => (value === null ? null : readRequiredStringValue(value, label));
const stringArray = (value: ApiResponsePayload, label: string): string[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => readRequiredStringValue(entry, `${label}[${String(index)}]`));
};
const recordArray = (value: ApiResponsePayload, label: string) => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => requireRecord(entry, `${label}[${String(index)}]`));
};
const decodeDevice = (value: ApiResponsePayload, label: string): OsNetworkDevice => {
    const record = requireRecord(value, label);
    return { device: readRequiredStringValue(record['device'], `${label}.device`), deviceType: nullableString(record['device_type'] ?? null, `${label}.device_type`), state: nullableString(record['state'] ?? null, `${label}.state`), connection: nullableString(record['connection'] ?? null, `${label}.connection`), ipv4Addresses: stringArray(record['ipv4_addresses'], `${label}.ipv4_addresses`), ipv4Gateway: nullableString(record['ipv4_gateway'] ?? null, `${label}.ipv4_gateway`), ipv4Dns: stringArray(record['ipv4_dns'], `${label}.ipv4_dns`), ipv6Addresses: stringArray(record['ipv6_addresses'], `${label}.ipv6_addresses`), ipv6Gateway: nullableString(record['ipv6_gateway'] ?? null, `${label}.ipv6_gateway`), ipv6Dns: stringArray(record['ipv6_dns'], `${label}.ipv6_dns`) };
};
const decodeConnection = (value: ApiResponsePayload, label: string): OsNetworkConnection => {
    const record = requireRecord(value, label);
    return { connectionId: readRequiredStringValue(record['connection_id'], `${label}.connection_id`), name: readRequiredStringValue(record['name'], `${label}.name`), connectionType: readRequiredStringValue(record['connection_type'], `${label}.connection_type`), device: nullableString(record['device'] ?? null, `${label}.device`), state: nullableString(record['state'] ?? null, `${label}.state`), active: readRequiredBooleanValue(record['active'], `${label}.active`), profileEditable: readRequiredBooleanValue(record['profile_editable'], `${label}.profile_editable`) };
};
const method = (value: ApiResponsePayload, label: string): 'auto' | 'manual' => {
    if (value !== 'auto' && value !== 'manual') throw new TypeError(`${label} must be auto or manual`);
    return value;
};
const decodeProfile = (value: ApiResponsePayload, label: string): OsNetworkConnectionProfile => {
    const record = requireRecord(value, label);
    return { connectionId: readRequiredStringValue(record['connection_id'], `${label}.connection_id`), name: readRequiredStringValue(record['name'], `${label}.name`), connectionType: readRequiredStringValue(record['connection_type'], `${label}.connection_type`), autoconnect: readRequiredBooleanValue(record['autoconnect'], `${label}.autoconnect`), ipv4Method: method(record['ipv4_method'], `${label}.ipv4_method`), ipv4Addresses: stringArray(record['ipv4_addresses'], `${label}.ipv4_addresses`), ipv4Gateway: readRequiredStringValue(record['ipv4_gateway'], `${label}.ipv4_gateway`), ipv4Dns: stringArray(record['ipv4_dns'], `${label}.ipv4_dns`), ipv6Method: method(record['ipv6_method'], `${label}.ipv6_method`), ipv6Addresses: stringArray(record['ipv6_addresses'], `${label}.ipv6_addresses`), ipv6Gateway: readRequiredStringValue(record['ipv6_gateway'], `${label}.ipv6_gateway`), ipv6Dns: stringArray(record['ipv6_dns'], `${label}.ipv6_dns`) };
};
const decodeOsNetworkStatus = (value: ApiResponsePayload): OsNetworkStatusResponse => {
    const record = requireRecord(value, 'OS network status');
    return { timestampMs: readRequiredFiniteNumberValue(record['timestamp_ms'], 'OS network status.timestamp_ms'), devices: recordArray(record['devices'], 'OS network status.devices').map((entry, index) => decodeDevice(entry, `OS network status.devices[${String(index)}]`)), connections: recordArray(record['connections'], 'OS network status.connections').map((entry, index) => decodeConnection(entry, `OS network status.connections[${String(index)}]`)) };
};
const decodeOsNetworkConnections = (value: ApiResponsePayload): OsNetworkConnectionsResponse => {
    const record = requireRecord(value, 'OS network connections');
    return { connections: recordArray(record['connections'], 'OS network connections.connections').map((entry, index) => decodeConnection(entry, `OS network connections.connections[${String(index)}]`)) };
};
const decodeOsNetworkDevices = (value: ApiResponsePayload): OsNetworkDevicesResponse => {
    const record = requireRecord(value, 'OS network devices');
    return { devices: recordArray(record['devices'], 'OS network devices.devices').map((entry, index) => decodeDevice(entry, `OS network devices.devices[${String(index)}]`)) };
};
const decodeOsNetworkProfile = (value: ApiResponsePayload): OsNetworkProfileResponse => {
    const record = requireRecord(value, 'OS network profile');
    return { profile: decodeProfile(record['profile'], 'OS network profile.profile') };
};

export { decodeOsNetworkConnections, decodeOsNetworkDevices, decodeOsNetworkProfile, decodeOsNetworkStatus };
export type { OsNetworkConnection, OsNetworkConnectionProfile, OsNetworkConnectionsResponse, OsNetworkDevice, OsNetworkDevicesResponse, OsNetworkProfileResponse, OsNetworkStatusResponse };
