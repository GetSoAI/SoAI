/* SoAI - Settings feature public contracts [frontend/assets/ts/features/settings/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

interface SettingItem {
    key: string;
    path: string;
    value: JsonValue;
}

interface AdvancedSettingsGroup {
    key: string;
    path: string;
    titleSegments: string[];
    settings: SettingItem[];
}

interface SectionItem {
    key: string;
    path: string;
    groups: AdvancedSettingsGroup[];
}

interface AnalyzeStructure {
    sections: SectionItem[];
}

interface TabDefinition {
    id: string;
    label: string;
    advanced: true;
    sectionKey?: string;
}

interface AdvancedSettingsRendererOptions {
    excludeSections?: ReadonlySet<string>;
}

interface RenderOptions {
    activeTabId?: string | null;
}

interface SectionOptions {
    title: string;
    content: DocumentFragment | Element | null;
}

export type { AdvancedSettingsGroup, AnalyzeStructure, RenderOptions, SectionOptions, SectionItem, SettingItem, TabDefinition, AdvancedSettingsRendererOptions };
