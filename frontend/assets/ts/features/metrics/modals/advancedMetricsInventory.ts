/* SoAI - Metrics advanced inventory builder [frontend/assets/ts/features/metrics/modals/advancedMetricsInventory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCurrentLocale } from '@core/languageservice/service.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type AdvancedMetricsInventoryRow = {
    label: string;
    value: string;
    monoValue: boolean;
    searchable: string;
};

type AdvancedMetricsInventorySection = {
    title: string;
    rows: AdvancedMetricsInventoryRow[];
};

type AdvancedMetricsInventory = {
    sections: AdvancedMetricsInventorySection[];
    copyText: string;
};

const formatValue = (value: JsonValue | undefined, placeholder: string): string => {
    if (value === null || value === undefined) {
        return placeholder;
    }
    if (typeof value === 'number') {
        return Number.isFinite(value) ? String(value) : placeholder;
    }
    if (typeof value === 'string') {
        const trimmed = value.trim();
        return trimmed ? trimmed : placeholder;
    }
    if (typeof value === 'boolean') {
        return String(value);
    }
    if (isArray(value)) {
        if (value.length === 0) {
            return placeholder;
        }
        const preview = value
            .slice(0, 8)
            .map((entry) => (entry === null || entry === undefined ? placeholder : String(entry)))
            .join(', ');
        return value.length > 8 ? `${preview}, …` : preview;
    }
    if (isObject(value)) {
        return placeholder;
    }
    return placeholder;
};

const normalizeSectionTitle = (value: string): string => {
    const trimmed = value.trim();
    return trimmed ? trimmed : '—';
};

const createRow = (label: string, value: JsonValue | undefined, placeholder: string): AdvancedMetricsInventoryRow => {
    const formatted = formatValue(value, placeholder);
    const monoValue = formatted.length > 32 || formatted.includes('/') || formatted.includes('\\') || formatted.includes('{') || formatted.includes('[');
    const normalizedLabel = label.trim();
    const normalizedValue = formatted.trim();
    const searchable = `${normalizedLabel} ${normalizedValue}`.toLowerCase();
    return { label: normalizedLabel, value: formatted, monoValue, searchable };
};

const appendFlattenedRows = (rows: AdvancedMetricsInventoryRow[], prefix: string, value: JsonValue | undefined, placeholder: string, depth: number): void => {
    if (depth <= 0) {
        rows.push(createRow(prefix, value, placeholder));
        return;
    }
    if (value === null || value === undefined) {
        rows.push(createRow(prefix, value, placeholder));
        return;
    }
    if (typeof value !== 'object') {
        rows.push(createRow(prefix, value, placeholder));
        return;
    }
    if (isArray(value)) {
        rows.push(createRow(prefix, value, placeholder));
        return;
    }
    if (!isObject(value)) {
        rows.push(createRow(prefix, value, placeholder));
        return;
    }
    const keys = Object.keys(value).sort((firstValue, secondValue) => firstValue.localeCompare(secondValue, getCurrentLocale()));
    if (keys.length === 0) {
        rows.push(createRow(prefix, placeholder, placeholder));
        return;
    }
    for (const key of keys) {
        const nextLabel = prefix ? `${prefix}.${key}` : key;
        appendFlattenedRows(rows, nextLabel, value[key], placeholder, depth - 1);
    }
};

const buildAdvancedMetricsInventory = (
    source: JsonValue | null,
    options: {
        placeholder: string;
        sectionTitles: Record<string, string>;
        otherSectionTitle: string;
        telemetrySectionTitle: string;
        telemetryStatus: JsonValue | null;
    }
): AdvancedMetricsInventory => {
    const placeholder = options.placeholder;
    const sections: AdvancedMetricsInventorySection[] = [];
    const copyLines: string[] = [];

    const appendSection = (title: string, sectionValue: JsonValue | null): void => {
        const rows: AdvancedMetricsInventoryRow[] = [];
        if (sectionValue !== null && sectionValue !== undefined) {
            appendFlattenedRows(rows, '', sectionValue, placeholder, 6);
        }
        rows.sort((firstValue, secondValue) => firstValue.label.localeCompare(secondValue.label, getCurrentLocale()));
        const normalizedTitle = normalizeSectionTitle(title);
        sections.push({ title: normalizedTitle, rows });
        copyLines.push(`[${normalizedTitle}]`);
        if (rows.length === 0) {
            copyLines.push(placeholder);
        } else {
            for (const row of rows) {
                copyLines.push(`${row.label}: ${row.value}`);
            }
        }
        copyLines.push('');
    };

    if (isObject(source)) {
        const keys = Object.keys(source).sort((firstValue, secondValue) => firstValue.localeCompare(secondValue, getCurrentLocale()));
        const handled = new Set<string>();

        for (const key of keys) {
            const title = options.sectionTitles[key];
            if (!title) {
                continue;
            }
            handled.add(key);
            appendSection(title, source[key] ?? null);
        }

        const remainingKeys = keys.filter((key) => !handled.has(key));
        if (remainingKeys.length > 0) {
            const other: JsonObject = {};
            for (const key of remainingKeys) {
                other[key] = source[key] ?? null;
            }
            appendSection(options.otherSectionTitle, other);
        }
    } else {
        appendSection(options.otherSectionTitle, source);
    }

    appendSection(options.telemetrySectionTitle, options.telemetryStatus);

    return { sections, copyText: copyLines.join('\n').trim() };
};

const filterAdvancedMetricsInventory = (inventory: AdvancedMetricsInventory, query: string): AdvancedMetricsInventory => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
        return inventory;
    }
    const tokens = normalized.split(/\s+/).filter((token) => token.length > 0);
    if (tokens.length === 0) {
        return inventory;
    }
    const sections = inventory.sections.map((section) => ({
        ...section,
        rows: section.rows.filter((row) => tokens.every((token) => row.searchable.includes(token)))
    }));
    const copyLines: string[] = [];
    for (const section of sections) {
        if (section.rows.length === 0) {
            continue;
        }
        copyLines.push(`[${section.title}]`);
        for (const row of section.rows) {
            copyLines.push(`${row.label}: ${row.value}`);
        }
        copyLines.push('');
    }
    return { sections, copyText: copyLines.join('\n').trim() };
};

export { buildAdvancedMetricsInventory, filterAdvancedMetricsInventory };
export type { AdvancedMetricsInventory, AdvancedMetricsInventoryRow, AdvancedMetricsInventorySection };
