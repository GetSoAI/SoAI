/* SoAI - Catalog feature capability presenter [frontend/assets/ts/features/catalog/capabilityPresenter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { OpenAICapabilities, PluginCapabilitiesExtended, PluginRecord } from '@core/types/pluginTypes.ts';
import { getOpenAIDescriptors, resolveOpenAIModalityDescriptor, resolveOpenAITokenDescriptor, type CapabilityDescriptor, type OpenAICategory } from '@features/catalog/openaiCapabilityDescriptors.ts';
import { PROVIDER_MODE, resolveProviderMode } from '@features/catalog/pluginNormalization.ts';

export type { OpenAICapabilities };
export type { CapabilityDescriptor, OpenAICategory };

const buildProviderDescriptor = (plugin: PluginRecord): CapabilityDescriptor | null => {
    const mode = resolveProviderMode(plugin);
    switch (mode) {
        case PROVIDER_MODE.PLUGIN_MANAGED:
            return {
                id: `provider-mode-${mode}`,
                label: i18n.t('plugins.providerMode.labels.pluginManaged'),
                title: i18n.t('plugins.providerMode.tooltips.pluginManaged'),
                className: 'capability-provider-managed'
            };
        case PROVIDER_MODE.USER_MANAGED:
            return {
                id: `provider-mode-${mode}`,
                label: i18n.t('plugins.providerMode.labels.userManaged'),
                title: i18n.t('plugins.providerMode.tooltips.userManaged'),
                className: 'capability-provider-user'
            };
        default:
            return null;
    }
};

export const getCapabilityDescriptors = (plugin: PluginRecord): CapabilityDescriptor[] => {
    const descriptors: CapabilityDescriptor[] = [];
    const usedIds = new Set<string>();

    if (plugin?.capabilities?.supportsModelDownload === true) {
        descriptors.push({ id: 'model-download', label: i18n.t('plugins.actions.downloadModel'), className: 'capability-model-download' });
        usedIds.add('model-download');
    }
    if (resolveProviderMode(plugin) !== PROVIDER_MODE.NONE) {
        descriptors.push({ id: 'external-providers', label: i18n.t('plugins.badges.providers'), className: 'capability-external-providers' });
        usedIds.add('external-providers');
    }
    if (plugin?.capabilities?.supportsBackendInstallation === true) {
        descriptors.push({ id: 'backend-install', label: i18n.t('plugins.badges.backend'), className: 'capability-backend-install' });
        usedIds.add('backend-install');
    }

    const capabilities: PluginCapabilitiesExtended | undefined = plugin.capabilities;
    const openai = capabilities?.openai;
    if (openai) {
        const dynamicDescriptors = getOpenAIDescriptors(openai);
        for (const descriptor of dynamicDescriptors) {
            if (!descriptor || usedIds.has(descriptor.id)) continue;
            descriptors.push(descriptor);
            usedIds.add(descriptor.id);
        }
    }

    const providerDescriptor = buildProviderDescriptor(plugin);
    if (providerDescriptor && !usedIds.has(providerDescriptor.id)) {
        descriptors.push(providerDescriptor);
        usedIds.add(providerDescriptor.id);
    }

    return descriptors;
};
export { PROVIDER_MODE, getOpenAIDescriptors, resolveOpenAIModalityDescriptor, resolveOpenAITokenDescriptor, resolveProviderMode };
export type { PluginCapabilitiesExtended };
