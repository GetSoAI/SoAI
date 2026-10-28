/* SoAI - Model detail page control layer OpenAI capabilities effects [frontend/assets/ts/pages/modeldetail/controllers/openaicapabilities/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBusyDisabledToken, setBusyDisabledState } from '@core/ui/controls/busyDisabledState.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { requireCatalogStore } from '@features/catalog/public.ts';
import { hasOpenAICapabilityOverrides, reconcileOpenAICapabilityControls, renderOpenAICapabilityOverrides, type OpenAICapabilityOverrideCategory, type OpenAICapabilityOverrideState } from '@features/models/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface ModelDetailOpenAICapabilityOverridesHost extends PageDomOwnerHost {
    model: ModelRecord | null;
    isVirtualModel(): boolean;
    getModelPluginName(): string;
    findPluginRecord(pluginName: string): PluginRecord | null;
    getOpenAICapabilityState(): OpenAICapabilityOverrideState | null;
    resolveOpenAICapabilityLabel(category: OpenAICapabilityOverrideCategory, token: string): string;
}

const syncModelDetailCapabilityButtons = (resetButton: HTMLButtonElement, state: OpenAICapabilityOverrideState | null): void => {
    const canReset = state !== null && hasOpenAICapabilityOverrides(state.current);
    const busyToken = getBusyDisabledToken(resetButton);
    if (busyToken) setBusyDisabledState(resetButton, { isBusy: false, token: busyToken });
    setControlDisabledState(resetButton, !canReset);
};

const populateModelDetailOpenAICapabilityOverrides = (host: ModelDetailOpenAICapabilityOverridesHost): void => {
    const card = host.pageDom.optionalHTMLElement('modeldetail-status-capabilities');
    const content = host.pageDom.optionalHTMLElement('modeldetail-status-capabilities-list');
    if (!card || !content) return;

    const resetButton = host.pageDom.optionalHTMLElement('modeldetail-openai-capabilities-reset');
    if (resetButton instanceof HTMLButtonElement) syncModelDetailCapabilityButtons(resetButton, host.isVirtualModel() ? null : host.getOpenAICapabilityState());

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
    reconcileOpenAICapabilityControls(content, markup);
    host.pageDom.removeClass(card, 'u-hidden');
};

export { populateModelDetailOpenAICapabilityOverrides, syncModelDetailCapabilityButtons };
