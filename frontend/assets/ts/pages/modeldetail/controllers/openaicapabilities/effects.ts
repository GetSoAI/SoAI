/* SoAI - Model detail page control layer OpenAI capabilities effects [frontend/assets/ts/pages/modeldetail/controllers/openaicapabilities/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';
import { hasOpenAICapabilityOverrideChanges, renderOpenAICapabilityOverrides, type OpenAICapabilityOverrideCategory, type OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ModelDetailOpenAICapabilityOverridesHost extends PageDomOwnerHost {
    model: ModelRecord | null;
    isVirtualModel(): boolean;
    getModelPluginName(): string;
    findPluginRecord(pluginName: string): PluginRecord | null;
    getOpenAICapabilityState(): OpenAICapabilityOverrideState | null;
    resolveOpenAICapabilityLabel(category: OpenAICapabilityOverrideCategory, token: string): string;
}

const populateModelDetailOpenAICapabilityOverrides = (host: ModelDetailOpenAICapabilityOverridesHost): void => {
    const card = host.pageDom.optionalHTMLElement('modeldetail-status-capabilities');
    const content = host.pageDom.optionalHTMLElement('modeldetail-status-capabilities-list');
    const resetButton = host.pageDom.optionalHTMLElement('modeldetail-openai-capabilities-reset');
    const saveButton = host.pageDom.optionalHTMLElement('modeldetail-openai-capabilities-save');
    if (!card || !content) return;

    if (!host.model || host.isVirtualModel()) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }

    const manifest = requireCatalogStore().getCapabilityManifest();
    const manifestObject = isJsonObject(manifest) ? manifest : null;
    const state = host.getOpenAICapabilityState();
    if (!state) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }
    const hasOverrides = state.currentDisabled.size > 0;
    const hasDirtyChanges = hasOpenAICapabilityOverrideChanges(state);
    if (resetButton instanceof HTMLButtonElement) {
        host.pageDom.updateProperty(resetButton, 'disabled', !hasOverrides || hasDirtyChanges);
        host.pageDom.toggleClass(resetButton, 'u-hidden', hasDirtyChanges);
    }
    if (saveButton instanceof HTMLButtonElement) {
        host.pageDom.updateProperty(saveButton, 'disabled', !hasDirtyChanges);
        host.pageDom.toggleClass(saveButton, 'u-hidden', !hasDirtyChanges);
    }

    const modelOpenAI = host.model.openaiCapabilities;
    if (!isJsonObject(modelOpenAI)) {
        host.pageDom.addClass(card, 'u-hidden');
        return;
    }

    const pluginName = host.getModelPluginName();
    const pluginRecord = pluginName ? host.findPluginRecord(pluginName) : null;
    const html = renderOpenAICapabilityOverrides({
        model: host.model,
        plugin: pluginRecord,
        manifest: manifestObject,
        state,
        host: {
            resolveOpenAICapabilityLabel: (category, token) => host.resolveOpenAICapabilityLabel(category, token)
        }
    });
    const markup = toTrustedUiHtml(html);
    host.pageDom.updateHtml(content, markup);
    host.pageDom.removeClass(card, 'u-hidden');
};

export { populateModelDetailOpenAICapabilityOverrides };
