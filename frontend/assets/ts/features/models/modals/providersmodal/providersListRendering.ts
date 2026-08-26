/* SoAI - Models feature providers list rendering [frontend/assets/ts/features/models/modals/providersmodal/providersListRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { MODELS_ACTION_DELETE_PROVIDER } from '@core/models/pageActions.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { ProviderData } from '@features/models/modals/providersmodal/contracts.ts';

const renderProvidersListMarkup = (providers: readonly ProviderData[], sanitizer: Pick<SanitizerApi, 'attribute' | 'html'>): TrustedHtml => {
    const deleteLabel = i18n.t('models.modal.providers.delete');
    const deleteIcon = getIconSync('close', { strokeWidth: 1.5 }).html;
    const statusLabel = i18n.t('models.modal.providers.statusLabel');
    const lastCheckedLabel = i18n.t('models.modal.providers.lastCheckedLabel');
    const lastErrorLabel = i18n.t('models.modal.providers.lastErrorLabel');
    const providersHtml = providers
        .map(
            (provider: ProviderData) => `
	                        <div class="provider-item" data-provider-id="${sanitizer.attribute(provider.id)}" data-plugin-name="${sanitizer.attribute(provider.pluginName)}">
	                            <div class="provider-info">
	                                <div class="provider-name" data-tooltip="${sanitizer.attribute(provider.name)}">${sanitizer.html(provider.name)}</div>
	                                <div class="provider-details">
                                    <span class="provider-plugin">${sanitizer.html(provider.pluginName)}</span>
                                    <span class="provider-url">${sanitizer.html(provider.apiUrl)}</span>
                                </div>
                                <div class="provider-availability">
                                    <div class="provider-availability-row">
                                        <span class="provider-availability-label">${sanitizer.html(statusLabel)}</span>
                                        <span class="${sanitizer.attribute(provider.availability.statusClassName)}" data-provider-status="${sanitizer.attribute(provider.lastStatus)}">${sanitizer.html(provider.availability.statusLabel)}</span>
                                    </div>
                                    <div class="provider-availability-row">
                                        <span class="provider-availability-label">${sanitizer.html(lastCheckedLabel)}</span>
                                        <span class="provider-availability-value">${sanitizer.html(provider.availability.checkedLabel)}</span>
                                    </div>
                                    <div class="provider-availability-row provider-availability-row--error">
                                        <span class="provider-availability-label">${sanitizer.html(lastErrorLabel)}</span>
                                        <span class="provider-availability-value provider-availability-error">${sanitizer.html(provider.availability.errorLabel)}</span>
                                    </div>
                                </div>
                            </div>
                            <div class="ui-collection-card__action-bar">
                                <button type="button"
                                        class="ui-round-button ui-round-button--delete"
                                        data-action="${sanitizer.attribute(MODELS_ACTION_DELETE_PROVIDER)}"
                                        data-provider-id="${sanitizer.attribute(provider.id)}"
                                        data-provider-revision="${sanitizer.attribute(String(provider.revision))}"
                                        data-plugin-name="${sanitizer.attribute(provider.pluginName)}"
                                        data-provider-name="${sanitizer.attribute(provider.name)}"
                                        aria-label="${sanitizer.attribute(deleteLabel)}"
                                        data-tooltip="${sanitizer.attribute(deleteLabel)}">${deleteIcon}</button>
	                            </div>
	                        </div>
	                    `
        )
        .join('');
    return toTrustedUiHtml(providersHtml);
};

export { renderProvidersListMarkup };
