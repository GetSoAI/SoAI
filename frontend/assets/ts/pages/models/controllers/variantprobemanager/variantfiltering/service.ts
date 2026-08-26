/* SoAI - Models page variant filtering service [frontend/assets/ts/pages/models/controllers/variantprobemanager/variantfiltering/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelVariantResponse, ModelVariantSpeedTest } from '@core/api/contracts/modelVariantContracts.ts';
import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';

const appendStringValue = (values: string[], value: string | null): void => {
    const trimmed = toTrimmedString(value);
    if (trimmed) {
        values.push(trimmed);
    }
};

const appendNumberValue = (values: string[], value: number | null): void => {
    if (value === null || !Number.isFinite(value)) {
        return;
    }
    values.push(String(value));
};

const appendBooleanValue = (values: string[], field: string, value: boolean | null): void => {
    if (value === null) {
        return;
    }
    values.push(field);
    values.push(`${field} ${String(value)}`);
    if (field === 'disk_fit') {
        values.push(value ? 'disk fits local disk ok' : 'disk exceeds local disk fail');
        return;
    }
    if (field === 'vram_fit') {
        values.push(value ? 'vram fits ok' : 'vram exceeds fail');
        return;
    }
    if (field === 'vram_ram_fit') {
        values.push(value ? 'vram ram memory fits ok' : 'vram ram memory exceeds fail');
        return;
    }
    if (field === 'runnable') {
        values.push(value ? 'runnable run capable ok' : 'not runnable cannot run fail');
    }
};

const appendSpeedTestText = (values: string[], source: ModelVariantSpeedTest | null): void => {
    if (!source) return;
    appendStringValue(values, source.mode);
    appendStringValue(values, source.storagePath);
    appendStringValue(values, source.interface);
    appendStringValue(values, source.detail);
};

const buildVariantSearchText = (variant: ModelVariantResponse): string => {
    const values: string[] = [];
    [variant.id, variant.name, variant.normalizedName, variant.description, variant.quantization, variant.checksum, variant.family, variant.advisory, variant.hardwareCompatibility, variant.hardwareCompatibilityLabel].forEach((value) => appendStringValue(values, value));
    [variant.sizeBytes, variant.sizeGb, variant.ramRequiredGb, variant.vramRequiredGb, variant.diskRequiredGb, variant.diskAvailableGb, variant.diskRemainingGb].forEach((value) => appendNumberValue(values, value));
    appendBooleanValue(values, 'disk_fit', variant.diskFit);
    appendBooleanValue(values, 'vram_fit', variant.vramFit);
    appendBooleanValue(values, 'vram_ram_fit', variant.vramRamFit);
    appendBooleanValue(values, 'runnable', variant.runnable);
    appendSpeedTestText(values, variant.speedTest);
    appendSpeedTestText(values, variant.networkSpeedTest);
    return values.join(' ').toLowerCase();
};

const resolveVariantFilterTokens = (query: string): string[] => {
    return toTrimmedLower(query).split(/\s+/).map(toTrimmedString).filter(Boolean);
};

const filterVariants = (variants: ModelVariantResponse[], query: string): ModelVariantResponse[] => {
    const tokens = resolveVariantFilterTokens(query);
    if (tokens.length === 0) {
        return variants.slice();
    }
    return variants.filter((variant) => {
        const text = buildVariantSearchText(variant);
        return Boolean(text) && tokens.every((token) => text.includes(token));
    });
};

export { filterVariants, resolveVariantFilterTokens };
