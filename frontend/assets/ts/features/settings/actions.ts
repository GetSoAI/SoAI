/* SoAI - Settings feature actions [frontend/assets/ts/features/settings/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatSentenceLabelFromId } from '@core/primitives/text.ts';
import { isArray, isBoolean, isNumber, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { AnalyzeStructure, SectionItem, TabDefinition } from '@features/settings/types.ts';

const formatSettingLabel = (key: string): string => formatSentenceLabelFromId(key);

const SETTING_PATH_SEGMENT_SEPARATOR = ' / ';
const CONFIG_PATH_SEGMENT_SEPARATOR = '.';

const formatSettingPathSegments = (segments: readonly string[]): string => segments.map((segment) => formatSettingLabel(segment)).join(SETTING_PATH_SEGMENT_SEPARATOR);

const formatConfigPathLabel = (configPath: string): string => formatSettingPathSegments(configPath.split(CONFIG_PATH_SEGMENT_SEPARATOR));

const sectionKeyToId = (sectionKey: string): string =>
    `advanced-${String(sectionKey ?? '')
        .toLowerCase()
        .replace(/_/g, '-')}`;

const createAdvancedTabs = (structure: AnalyzeStructure | null): TabDefinition[] => {
    if (!structure) {
        return [];
    }
    const tabs: TabDefinition[] = [];
    if (isArray(structure.sections) && structure.sections.length > 0) {
        structure.sections.forEach((section: SectionItem): void => {
            if (isString(section?.key) && section.key) {
                tabs.push({
                    id: sectionKeyToId(section.key),
                    label: formatSettingLabel(section.key),
                    advanced: true,
                    sectionKey: section.key
                });
            }
        });
    }
    return tabs;
};

const resolveHelpText = (key: string, value: JsonValue): string => {
    const lowerKey = isString(key) ? key.toLowerCase() : '';
    if (lowerKey.includes('port')) return i18n.t('settings.advanced.helpText.port');
    if (lowerKey.includes('host')) return i18n.t('settings.advanced.helpText.host');
    if (lowerKey.includes('path')) return i18n.t('settings.advanced.helpText.path');
    if (lowerKey.includes('enabled')) return i18n.t('settings.advanced.helpText.enabled');
    if (lowerKey.includes('timeout')) return i18n.t('settings.advanced.helpText.timeout');
    if (lowerKey.includes('interval')) return i18n.t('settings.advanced.helpText.interval');
    if (lowerKey.includes('limit')) return i18n.t('settings.advanced.helpText.limit');
    if (lowerKey.includes('count')) return i18n.t('settings.advanced.helpText.count');
    if (lowerKey.includes('size')) return i18n.t('settings.advanced.helpText.size');
    if (lowerKey.includes('level')) return i18n.t('settings.advanced.helpText.level');

    if (value === null || value === undefined) {
        return i18n.t('settings.advanced.helpText.defaultGeneric');
    }
    if (isBoolean(value)) {
        return i18n.t('settings.advanced.helpText.booleanGeneric');
    }
    if (isNumber(value)) {
        return i18n.t('settings.advanced.helpText.numericGeneric');
    }
    if (isArray(value)) {
        return i18n.t('settings.advanced.helpText.arrayGeneric');
    }
    if (isJsonObject(value)) {
        return i18n.t('settings.advanced.helpText.objectGeneric');
    }
    return i18n.t('settings.advanced.helpText.defaultGeneric');
};

export { createAdvancedTabs, formatConfigPathLabel, sectionKeyToId, formatSettingLabel, formatSettingPathSegments, resolveHelpText };
