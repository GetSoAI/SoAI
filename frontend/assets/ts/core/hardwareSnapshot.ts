/* SoAI - Shared frontend hardware snapshot [frontend/assets/ts/core/hardwareSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonArray, isJsonObject, type JsonArray, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const readJsonObjectProperty = (value: JsonObject | null, key: string): JsonObject | null => {
    if (!value) {
        return null;
    }
    const candidate = value[key];
    return isJsonObject(candidate) ? candidate : null;
};

const readJsonArrayProperty = (value: JsonObject | null, key: string): JsonArray | null => {
    if (!value) {
        return null;
    }
    const candidate = value[key];
    return isJsonArray(candidate) ? candidate : null;
};

const readGpuDevices = (snapshot: JsonObject): JsonArray | null => {
    const directGpu = readJsonObjectProperty(snapshot, 'gpu');
    const directDevices = readJsonArrayProperty(directGpu, 'gpus');
    if (directDevices) {
        return directDevices;
    }
    const directRootDevices = readJsonArrayProperty(snapshot, 'gpus');
    if (directRootDevices) {
        return directRootDevices;
    }
    const hardware = readJsonObjectProperty(snapshot, 'hardware');
    const nestedGpu = readJsonObjectProperty(hardware, 'gpu');
    const nestedDevices = readJsonArrayProperty(nestedGpu, 'gpus');
    if (nestedDevices) {
        return nestedDevices;
    }
    return readJsonArrayProperty(hardware, 'gpus');
};

const hardwareSnapshotHasGpu = (value: JsonValue | null | undefined): boolean => {
    if (!isJsonObject(value)) {
        return false;
    }
    const devices = readGpuDevices(value);
    return devices !== null && devices.length > 0;
};

export { hardwareSnapshotHasGpu };
