/* SoAI - Settings feature service [frontend/assets/ts/features/settings/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { dom } from '@core/dom/dom.ts';
import { isArray, isSet, isString } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { AdvancedSettingsRendererOptions, AnalyzeStructure, RenderOptions, TabDefinition } from '@features/settings/types.ts';
import { createAdvancedTabs, formatSettingLabel, sectionKeyToId } from '@features/settings/actions.ts';
import { analyzeAdvancedPresentation, resolveSectionByKey } from '@features/settings/advancedPresentation.ts';
import { createAdvancedSection, createAdvancedTabContent, renderAdvancedGroups } from '@features/settings/dom.ts';

class AdvancedSettingsRenderer {
    readonly excludeSections: ReadonlySet<string>;

    constructor(options: AdvancedSettingsRendererOptions = {}) {
        const { excludeSections = new Set<string>() } = options;
        this.excludeSections = isSet(excludeSections) ? excludeSections : new Set<string>();
    }

    analyze(config: JsonObject = {}): AnalyzeStructure {
        if (!isJsonObject(config)) {
            return { sections: [] };
        }
        return analyzeAdvancedPresentation(config, this.excludeSections);
    }

    createTabs(structure: AnalyzeStructure | null): TabDefinition[] {
        return createAdvancedTabs(structure);
    }

    render(structure: AnalyzeStructure | null, options: RenderOptions = {}): DocumentFragment {
        const { activeTabId = null } = options;
        const fragment = dom.createFragment();
        if (!structure) {
            return fragment;
        }

        if (isArray(structure.sections) && structure.sections.length > 0) {
            structure.sections.forEach((section) => {
                if (!section || !section.key) {
                    return;
                }
                const tabId = sectionKeyToId(section.key);
                const tabContent = createAdvancedTabContent(tabId, activeTabId === tabId);
                const nestedContent = renderAdvancedGroups(section.groups);
                const sectionElement = createAdvancedSection({
                    title: i18n.t('settings.advanced.sectionHeader'),
                    content: nestedContent
                });
                dom.appendChild(tabContent, sectionElement);
                dom.appendChild(fragment, tabContent);
            });
        }

        return fragment;
    }

    renderSectionContent(sectionKey: string, config: JsonObject = {}): DocumentFragment | null {
        if (!isString(sectionKey) || !sectionKey || !isJsonObject(config)) {
            return null;
        }
        const structure = this.analyze(config);
        const section = resolveSectionByKey(structure, sectionKey);
        if (!section) {
            return null;
        }
        return renderAdvancedGroups(section.groups);
    }

    formatSectionLabel(key: string): string {
        return formatSettingLabel(key);
    }
}

const createAdvancedSettingsRenderer = (options: AdvancedSettingsRendererOptions = {}): AdvancedSettingsRenderer => new AdvancedSettingsRenderer(options);

export { AdvancedSettingsRenderer, createAdvancedSettingsRenderer };
export type { AdvancedSettingsRendererOptions, AnalyzeStructure, TabDefinition };
