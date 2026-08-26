/* SoAI - Model detail page control layer view service [frontend/assets/ts/pages/modeldetail/controllers/page/view/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import { getWindowOpen } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import { createModelDetailCardSectionsHost, createModelDetailModelInfoHost } from '@pages/modeldetail/controllers/page/view/mappers.ts';
import type { ModelDetailViewHost } from '@pages/modeldetail/controllers/page/view/types.ts';
import { resolveModelDetailBackendDocumentation } from '@pages/modeldetail/formatting/modelDetailBackendDocumentation.ts';
import { populateModelDetailCapabilityBadges, populateModelDetailExternalProviderCard, populateModelDetailInferenceDefaults, populateModelDetailPluginInfoCard, updateModelDetailCardVisibility } from '@pages/modeldetail/rendering/modelDetailCardSections.ts';
import { populateModelDetailModelInfo } from '@pages/modeldetail/rendering/modelDetailModelInfoSection.ts';

const populateModelDetailCards = (host: ModelDetailViewHost): void => {
    const cardHost = createModelDetailCardSectionsHost(host);
    populateModelDetailExternalProviderCard(cardHost);
    populateModelDetailPluginInfoCard(cardHost);
    updateModelDetailCardVisibility(cardHost);
    populateModelDetailInferenceDefaults(cardHost);
    populateModelDetailCapabilityBadges(cardHost);
};

const populateModelDetailModelInformation = (host: ModelDetailViewHost): void => {
    if (!host.state.model) {
        return;
    }
    populateModelDetailModelInfo(
        createModelDetailModelInfoHost(host, {
            updateBackendDocButtonVisibility: () => updateModelDetailBackendDocButtonVisibility(host),
            populateDetailCards: () => populateModelDetailCards(host)
        })
    );
};

const setModelDetailPageState = (host: ModelDetailViewHost, state: string): void => {
    const isErrorState = state === 'error';
    const ui = host.state.ensureUi();
    host.state.pageDom.toggleClass(ui.overviewContent, 'u-hidden', isErrorState);
    host.state.pageDom.toggleClass(ui.parametersContent, 'u-hidden', isErrorState);
    host.state.pageDom.toggleClass(ui.modelDetailError, 'u-hidden', !isErrorState);
};

const updateModelDetailBackendDocumentationLink = async (host: ModelDetailViewHost, options: { ensurePlugins?: boolean; plugins?: JsonValue[] | null } = {}): Promise<{ backendDocumentationUrl: string | null; pluginCollectionSnapshot: JsonValue[] }> => {
    const resolved = resolveModelDetailBackendDocumentation(
        {
            model: host.state.model,
            pluginCollectionSnapshot: host.state.pluginCollectionSnapshot,
            getResource: (resource: string, resourceOptions?: Record<string, JsonValue>): JsonValue | ResourceSnapshot | null => {
                return host.state.streamManager.resources.getResource(resource, resourceOptions ?? {});
            }
        },
        options
    );
    return { backendDocumentationUrl: resolved.url, pluginCollectionSnapshot: resolved.pluginCollectionSnapshot };
};

const updateModelDetailBackendDocButtonVisibility = (host: ModelDetailViewHost): void => {
    const button = host.state.pageDom.optionalHTMLElement('#backend-doc-button');
    if (!(button instanceof HTMLAnchorElement)) {
        return;
    }
    const isAvailable = !!host.state.backendDocumentationUrl;
    host.state.pageDom.updateAttribute(button, 'href', isAvailable ? host.state.backendDocumentationUrl : null);
    host.state.pageDom.updateAttribute(button, 'aria-disabled', isAvailable ? null : 'true');
    host.state.pageDom.updateAttribute(button, 'tabindex', isAvailable ? null : '-1');
};

const handleModelDetailBackendDocumentationClick = async (host: ModelDetailViewHost): Promise<void> => {
    if (!host.state.backendDocumentationUrl) {
        return;
    }
    const confirmed = await requireDialogsService().showExternalLinkModal({
        title: i18n.t('modelDetail.confirmations.externalLink'),
        message: i18n.t('modelDetail.confirmations.externalLinkMessage'),
        url: host.state.backendDocumentationUrl,
        confirmText: i18n.t('modelDetail.confirmations.externalLinkConfirm'),
        cancelText: i18n.t('modelDetail.confirmations.externalLinkCancel'),
        variant: 'info',
        icon: 'external-link'
    });
    if (confirmed) {
        getWindowOpen()(host.state.backendDocumentationUrl, '_blank', 'noopener,noreferrer');
    }
};

export { handleModelDetailBackendDocumentationClick, populateModelDetailCards, populateModelDetailModelInformation, setModelDetailPageState, updateModelDetailBackendDocButtonVisibility, updateModelDetailBackendDocumentationLink };
