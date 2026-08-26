/* SoAI - Hardware snapshot operating-system V1 boundary decoding [frontend/assets/ts/core/api/contracts/hardwareSnapshotSystemContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareOperatingSystemSnapshot } from '@core/api/contracts/hardwareContractTypes.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const decodeHardwareOperatingSystemSnapshot = (value: JsonValue): HardwareOperatingSystemSnapshot => {
    const record = requireRecord(value, 'Hardware snapshot.os');
    const decoded: HardwareOperatingSystemSnapshot = {};
    const system = readNullableTrimmedStringValue(record['system'], 'Hardware snapshot.os.system') ?? undefined;
    const nodeName = readNullableTrimmedStringValue(record['node_name'], 'Hardware snapshot.os.node_name') ?? undefined;
    const release = readNullableTrimmedStringValue(record['release'], 'Hardware snapshot.os.release') ?? undefined;
    const version = readNullableTrimmedStringValue(record['version'], 'Hardware snapshot.os.version') ?? undefined;
    const machine = readNullableTrimmedStringValue(record['machine'], 'Hardware snapshot.os.machine') ?? undefined;
    const processor = readNullableTrimmedStringValue(record['processor'], 'Hardware snapshot.os.processor') ?? undefined;
    if (system !== undefined) decoded.system = system;
    if (nodeName !== undefined) decoded.nodeName = nodeName;
    if (release !== undefined) decoded.release = release;
    if (version !== undefined) decoded.version = version;
    if (machine !== undefined) decoded.machine = machine;
    if (processor !== undefined) decoded.processor = processor;
    return decoded;
};

export { decodeHardwareOperatingSystemSnapshot };
