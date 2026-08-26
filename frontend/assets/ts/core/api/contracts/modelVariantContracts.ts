/* SoAI - Shared frontend API contract boundary model variant contracts [frontend/assets/ts/core/api/contracts/modelVariantContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readNullableFiniteNumberValue, readNullableNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableBooleanValue, readNullableTrimmedStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

type ModelVariantSpeedStatus = 'ready' | 'unavailable';

interface ModelVariantSpeedTest {
    status: ModelVariantSpeedStatus;
    observedAtMs: number | null;
    durationMs: number | null;
    bytesDownloaded: number | null;
    bytesPerSecond: number | null;
    estimatedMs: number | null;
    baseEstimatedMs: number | null;
    estimationFactor: number | null;
    sizeBytes: number | null;
    sampleBytes: number | null;
    mode: string | null;
    storagePath: string | null;
    interface: string | null;
    detail: string | null;
}

interface ModelVariantResponse {
    id: string;
    name: string;
    normalizedName: string;
    description: string | null;
    quantization: string | null;
    sizeBytes: number | null;
    sizeGb: number | null;
    ramRequiredGb: number | null;
    vramRequiredGb: number | null;
    checksum: string | null;
    family: string | null;
    diskFit: boolean | null;
    diskRequiredGb: number | null;
    diskAvailableGb: number | null;
    vramFit: boolean | null;
    vramRamFit: boolean | null;
    advisory: string | null;
    runnable: boolean | null;
    hardwareCompatibility: string | null;
    hardwareCompatibilityLabel: string | null;
    diskRemainingGb: number | null;
    speedTest: ModelVariantSpeedTest | null;
    networkSpeedTest: ModelVariantSpeedTest | null;
}

const decodeSpeedStatus = (value: JsonValue | undefined, label: string): ModelVariantSpeedStatus => {
    if (value !== 'ready' && value !== 'unavailable') {
        throw new TypeError(`${label} must be ready or unavailable.`);
    }
    return value;
};

const decodeSpeedTest = (value: JsonValue | undefined, label: string): ModelVariantSpeedTest | null => {
    if (value === null || value === undefined) return null;
    const record = requireRecord(value, label);
    return {
        status: decodeSpeedStatus(record['status'], `${label}.status`),
        observedAtMs: readNullableNonNegativeIntegerValue(record['observed_at_ms'], `${label}.observed_at_ms`),
        durationMs: readNullableNonNegativeIntegerValue(record['duration_ms'], `${label}.duration_ms`),
        bytesDownloaded: readNullableNonNegativeIntegerValue(record['bytes_downloaded'], `${label}.bytes_downloaded`),
        bytesPerSecond: readNullableFiniteNumberValue(record['bytes_per_second'], `${label}.bytes_per_second`),
        estimatedMs: readNullableNonNegativeIntegerValue(record['estimated_ms'], `${label}.estimated_ms`),
        baseEstimatedMs: readNullableNonNegativeIntegerValue(record['base_estimated_ms'], `${label}.base_estimated_ms`),
        estimationFactor: readNullableFiniteNumberValue(record['estimation_factor'], `${label}.estimation_factor`),
        sizeBytes: readNullableNonNegativeIntegerValue(record['size_bytes'], `${label}.size_bytes`),
        sampleBytes: readNullableNonNegativeIntegerValue(record['sample_bytes'], `${label}.sample_bytes`),
        mode: readNullableTrimmedStringValue(record['mode'], `${label}.mode`),
        storagePath: readNullableTrimmedStringValue(record['storage_path'], `${label}.storage_path`),
        interface: readNullableTrimmedStringValue(record['interface'], `${label}.interface`),
        detail: readNullableTrimmedStringValue(record['detail'], `${label}.detail`)
    };
};

const decodeModelVariant = (value: JsonValue, index: number): ModelVariantResponse => {
    const label = `Model variant response[${String(index)}]`;
    const record = requireRecord(value, label);
    return {
        id: readRequiredTrimmedString(record, 'id', `${label}.id`),
        name: readRequiredTrimmedString(record, 'name', `${label}.name`),
        normalizedName: readRequiredTrimmedString(record, 'normalized_name', `${label}.normalized_name`),
        description: readNullableTrimmedStringValue(record['description'], `${label}.description`),
        quantization: readNullableTrimmedStringValue(record['quantization'], `${label}.quantization`),
        sizeBytes: readNullableNonNegativeIntegerValue(record['size_bytes'], `${label}.size_bytes`),
        sizeGb: readNullableFiniteNumberValue(record['size_gb'], `${label}.size_gb`),
        ramRequiredGb: readNullableFiniteNumberValue(record['ram_required_gb'], `${label}.ram_required_gb`),
        vramRequiredGb: readNullableFiniteNumberValue(record['vram_required_gb'], `${label}.vram_required_gb`),
        checksum: readNullableTrimmedStringValue(record['checksum'], `${label}.checksum`),
        family: readNullableTrimmedStringValue(record['family'], `${label}.family`),
        diskFit: readNullableBooleanValue(record['disk_fit'], `${label}.disk_fit`),
        diskRequiredGb: readNullableFiniteNumberValue(record['disk_required_gb'], `${label}.disk_required_gb`),
        diskAvailableGb: readNullableFiniteNumberValue(record['disk_available_gb'], `${label}.disk_available_gb`),
        vramFit: readNullableBooleanValue(record['vram_fit'], `${label}.vram_fit`),
        vramRamFit: readNullableBooleanValue(record['vram_ram_fit'], `${label}.vram_ram_fit`),
        advisory: readNullableTrimmedStringValue(record['advisory'], `${label}.advisory`),
        runnable: readNullableBooleanValue(record['runnable'], `${label}.runnable`),
        hardwareCompatibility: readNullableTrimmedStringValue(record['hardware_compatibility'], `${label}.hardware_compatibility`),
        hardwareCompatibilityLabel: readNullableTrimmedStringValue(record['hardware_compatibility_label'], `${label}.hardware_compatibility_label`),
        diskRemainingGb: readNullableFiniteNumberValue(record['disk_remaining_gb'], `${label}.disk_remaining_gb`),
        speedTest: decodeSpeedTest(record['speed_test'], `${label}.speed_test`),
        networkSpeedTest: decodeSpeedTest(record['network_speed_test'], `${label}.network_speed_test`)
    };
};

const decodeModelVariantsResponse = (value: ApiResponsePayload): ModelVariantResponse[] => {
    if (!Array.isArray(value)) {
        throw new TypeError('Model variants response must be an array.');
    }
    return value.map(decodeModelVariant);
};

export { decodeModelVariantsResponse };
export type { ModelVariantResponse, ModelVariantSpeedStatus, ModelVariantSpeedTest };
