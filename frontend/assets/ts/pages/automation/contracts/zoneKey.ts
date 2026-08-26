/* SoAI - Automation page zone key [frontend/assets/ts/pages/automation/contracts/zoneKey.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isEpochMsNumber } from '@core/time/epochMs.ts';
import type { AutomationZone } from '@features/automation/public.ts';

const INTEGER_TEXT_PATTERN = /^\d+$/;

const buildAutomationZoneKey = (automationId: string, scheduledAtMs: number): string => {
    const id = automationId.trim();
    if (!id) {
        throw new Error('Automation zone key requires a non-empty automation id');
    }
    if (!isEpochMsNumber(scheduledAtMs)) {
        throw new Error('Automation zone key requires a valid scheduled UTC timestamp');
    }
    return `${id}:${scheduledAtMs}`;
};

const buildAutomationZoneKeyForZone = (zone: Pick<AutomationZone, 'automationId' | 'scheduledAtMs'>): string => buildAutomationZoneKey(zone.automationId, zone.scheduledAtMs);

const resolveAutomationZoneByKey = (zones: readonly AutomationZone[], key: string): AutomationZone | null => {
    const token = key.trim();
    if (!token) {
        return null;
    }
    const parsed = parseAutomationZoneKey(token, 'Automation zone lookup');
    for (const zone of zones) {
        if (zone.automationId === parsed.automationId && zone.scheduledAtMs === parsed.scheduledAtMs) {
            return zone;
        }
    }
    return null;
};

const normalizeAutomationZoneKeyList = (zoneKeys: readonly string[]): string[] => {
    const normalized: string[] = [];
    const seen = new Set<string>();
    for (const key of zoneKeys) {
        const token = key.trim();
        if (!token || seen.has(token)) {
            continue;
        }
        seen.add(token);
        normalized.push(token);
    }
    return normalized;
};

const parseAutomationZoneKey = (key: string, label: string): { automationId: string; scheduledAtMs: number } => {
    const raw = key.trim();
    if (!raw) {
        throw new Error(`${label} requires a zone key`);
    }
    const index = raw.lastIndexOf(':');
    if (index <= 0 || index >= raw.length - 1) {
        throw new Error(`${label} has an invalid zone key format`);
    }
    const automationId = raw.slice(0, index).trim();
    const utcMsCandidate = raw.slice(index + 1).trim();
    if (!automationId) {
        throw new Error(`${label} has an invalid zone key automation id`);
    }
    if (!INTEGER_TEXT_PATTERN.test(utcMsCandidate)) {
        throw new Error(`${label} has an invalid zone key timestamp`);
    }
    const scheduledAtMs = Number(utcMsCandidate);
    if (!isEpochMsNumber(scheduledAtMs)) {
        throw new Error(`${label} has an invalid zone key timestamp`);
    }
    return { automationId, scheduledAtMs };
};

export { buildAutomationZoneKey, buildAutomationZoneKeyForZone, normalizeAutomationZoneKeyList, parseAutomationZoneKey, resolveAutomationZoneByKey };
