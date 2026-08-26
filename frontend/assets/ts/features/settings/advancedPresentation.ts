/* SoAI - Settings feature advanced presentation [frontend/assets/ts/features/settings/advancedPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { AdvancedSettingsGroup, AnalyzeStructure, SectionItem, SettingItem } from '@features/settings/types.ts';

interface AdvancedSettingsChildNode {
    key: string;
    path: string;
    value: JsonObject;
}

interface AdvancedSettingsNodeParts {
    settings: SettingItem[];
    childNodes: AdvancedSettingsChildNode[];
}

const createSettingPath = (basePath: string, key: string): string => `${basePath}.${key}`;

const createGroup = (path: string, titleSegments: readonly string[], settings: SettingItem[]): AdvancedSettingsGroup => {
    const resolvedTitleSegments = titleSegments.length > 0 ? [...titleSegments] : [path];
    const key = resolvedTitleSegments[resolvedTitleSegments.length - 1] ?? path;
    return {
        key,
        path,
        titleSegments: resolvedTitleSegments,
        settings
    };
};

const splitNodeParts = (record: JsonObject, basePath: string): AdvancedSettingsNodeParts => {
    const settings: SettingItem[] = [];
    const childNodes: AdvancedSettingsChildNode[] = [];
    for (const [key, value] of Object.entries(record)) {
        if (!isString(key) || !key) {
            continue;
        }
        const path = createSettingPath(basePath, key);
        if (isJsonObject(value)) {
            if (Object.keys(value).length > 0) {
                childNodes.push({ key, path, value });
            }
            continue;
        }
        settings.push({ key, path, value });
    }
    return { settings, childNodes };
};

const createChildTitleSegments = (titleSegments: readonly string[], childKey: string, parentHasSettings: boolean): string[] => {
    if (parentHasSettings || titleSegments.length === 0) {
        return [childKey];
    }
    return [...titleSegments, childKey];
};

const buildGroupsForNode = (record: JsonObject, path: string, titleSegments: readonly string[]): AdvancedSettingsGroup[] => {
    const parts = splitNodeParts(record, path);
    const groups: AdvancedSettingsGroup[] = [];
    const parentHasSettings = parts.settings.length > 0;
    if (parentHasSettings) {
        groups.push(createGroup(path, titleSegments, parts.settings));
    }
    for (const childNode of parts.childNodes) {
        const childTitleSegments = createChildTitleSegments(titleSegments, childNode.key, parentHasSettings);
        groups.push(...buildGroupsForNode(childNode.value, childNode.path, childTitleSegments));
    }
    return groups;
};

const buildActualSections = (config: JsonObject, excludeSections: ReadonlySet<string>): SectionItem[] => {
    const sections: SectionItem[] = [];
    for (const [key, value] of Object.entries(config)) {
        if (!isString(key) || !key || excludeSections.has(key)) {
            continue;
        }
        if (!isJsonObject(value)) {
            continue;
        }
        if (Object.keys(value).length === 0) {
            continue;
        }
        const groups = buildGroupsForNode(value, key, []);
        if (groups.length === 0) {
            continue;
        }
        sections.push({ key, path: key, groups });
    }
    return sections;
};

const analyzeAdvancedPresentation = (config: JsonObject, excludeSections: ReadonlySet<string>): AnalyzeStructure => ({
    sections: buildActualSections(config, excludeSections)
});

const resolveSectionByKey = (structure: AnalyzeStructure, sectionKey: string): SectionItem | null => {
    for (const section of structure.sections) {
        if (section.key === sectionKey) {
            return section;
        }
    }
    return null;
};

export { analyzeAdvancedPresentation, resolveSectionByKey };
