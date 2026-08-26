/* SoAI - Settings feature DOM contracts [frontend/assets/ts/features/settings/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isDocumentFragment } from '@core/dom/domEnvironment.ts';
import { i18n } from '@core/i18n/index.ts';
import { isElementNode } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { createToggleSwitch } from '@core/toggleSwitch.ts';
import { describeSettingControl } from '@features/settings/configControlDescriptors.ts';
import type { AdvancedSettingsGroup, SettingItem, SectionOptions } from '@features/settings/types.ts';
import { formatSettingLabel, formatSettingPathSegments, resolveHelpText } from '@features/settings/actions.ts';

const createAdvancedTabContent = (tabId: string, isActive: boolean): HTMLElement => {
    const container = dom.create('div', {
        className: 'tab-content',
        id: `${tabId}-content`,
        dataset: { tabType: 'advanced' },
        role: 'tabpanel',
        'aria-labelledby': `${tabId}-tab`
    });
    if (isActive) {
        dom.addClass(container, 'is-active');
    }
    return container;
};

const createAdvancedSection = ({ title, content }: SectionOptions): HTMLElement => {
    const section = dom.create('div', { className: 'settings-section' });
    const header = dom.create('div', { className: 'section-header' });
    const heading = dom.create('h2', { className: 'section-title', textContent: title });
    dom.appendChild(header, heading);
    dom.appendChild(section, header);

    const sectionContent = dom.create('div', { className: 'section-content' });
    if (isDocumentFragment(content) || isElementNode(content)) {
        dom.appendChild(sectionContent, content);
    }
    dom.appendChild(section, sectionContent);
    return section;
};

const createSettingControl = (value: JsonValue, path: string): HTMLElement => {
    const descriptor = describeSettingControl(value, path, 'advanced');
    if (descriptor.controlType === 'text') {
        return dom.create('input', {
            type: 'text',
            className: 'setting-input',
            id: descriptor.id,
            dataset: { path: descriptor.path },
            placeholder: descriptor.placeholder ?? '',
            value: descriptor.value
        });
    }
    if (descriptor.controlType === 'toggle') {
        return createToggleSwitch({
            id: descriptor.id,
            checked: descriptor.checked,
            labels: {
                trueLabel: i18n.t('settings.advanced.booleanTrue'),
                falseLabel: i18n.t('settings.advanced.booleanFalse')
            },
            inputDataset: { path: descriptor.path }
        });
    }
    if (descriptor.controlType === 'number') {
        return dom.create('input', {
            type: 'number',
            className: 'setting-input',
            id: descriptor.id,
            dataset: { path: descriptor.path },
            value: descriptor.value
        });
    }
    return dom.create('textarea', {
        className: descriptor.className,
        id: descriptor.id,
        dataset: { path: descriptor.path },
        rows: descriptor.rows,
        value: descriptor.value
    });
};

const createSettingItem = (setting: SettingItem): HTMLElement | null => {
    if (!setting || !setting.key) {
        return null;
    }
    const container = dom.create('div', {
        className: 'setting-item setting-change-surface',
        dataset: { path: setting.path }
    });

    const info = dom.create('div', { className: 'setting-info' });
    const label = dom.create('label', {
        className: 'setting-label',
        textContent: formatSettingLabel(setting.key)
    });
    dom.appendChild(info, label);

    const help = dom.create('span', {
        className: 'setting-help',
        textContent: resolveHelpText(setting.key, setting.value)
    });
    dom.appendChild(info, help);

    const controlWrapper = dom.create('div', { className: 'setting-control' });
    const control = createSettingControl(setting.value, setting.path);
    if (control) {
        dom.appendChild(controlWrapper, control);
    }

    dom.appendChild(container, [info, controlWrapper]);
    return container;
};

const createSettingsGroup = (settings: SettingItem[]): HTMLElement => {
    const group = dom.create('div', { className: 'settings-group' });
    settings.forEach((setting: SettingItem) => {
        const item = createSettingItem(setting);
        if (item) {
            dom.appendChild(group, item);
        }
    });
    return group;
};

const formatGroupTitle = (group: AdvancedSettingsGroup): string => formatSettingPathSegments(group.titleSegments);

const createSettingsSubgroup = (title: string, settings: SettingItem[]): HTMLElement => {
    const container = dom.create('div', { className: 'settings-subgroup' });
    const header = dom.create('div', { className: 'subgroup-header' });
    const heading = dom.create('h3', {
        className: 'subgroup-title',
        textContent: title
    });
    dom.appendChild(header, heading);
    dom.appendChild(container, header);
    dom.appendChild(container, createSettingsGroup(settings));
    return container;
};

const renderAdvancedGroups = (groups: AdvancedSettingsGroup[]): DocumentFragment => {
    const fragment = dom.createFragment();
    groups.forEach((group) => {
        if (group.settings.length === 0) {
            return;
        }
        dom.appendChild(fragment, createSettingsSubgroup(formatGroupTitle(group), group.settings));
    });
    return fragment;
};

export { createAdvancedSection, createAdvancedTabContent, createSettingControl, createSettingItem, createSettingsGroup, renderAdvancedGroups };
