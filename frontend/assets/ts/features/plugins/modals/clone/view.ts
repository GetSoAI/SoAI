/* SoAI - Plugins feature clone rendering [frontend/assets/ts/features/plugins/modals/clone/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { CloneManagerHost, SecurityService } from '@features/plugins/modals/clone/types.ts';

interface ClonePluginInfoMarkupOptions {
    modalId: string;
    plugin: PluginRecord;
    host: CloneManagerHost;
    security: SecurityService;
    pluginStatus: string;
    displayName: string;
}

const renderClonePluginInfoMarkup = ({ modalId, plugin, host, security, pluginStatus, displayName }: ClonePluginInfoMarkupOptions): TrustedHtml => {
    const statusText = host.policy.statusManager.getDescription(pluginStatus);
    const statusHtml = i18n.t('plugins.modal.clonePlugin.status', {
        status: host.policy.sanitizeText(statusText)
    });
    const versionValue = toTrimmedString(plugin.versionSoaiplugin);
    const versionHtml = i18n.t('plugins.modal.clonePlugin.version', {
        version: security.escapeHtml(versionValue ? versionValue : i18n.t('common.notAvailableShort'))
    });
    const authorValue = toTrimmedString(plugin.authorSoaiplugin);
    const authorHtml = i18n.t('plugins.modal.clonePlugin.author', {
        author: security.escapeHtml(authorValue ? authorValue : i18n.t('common.unknown'))
    });
    const cloneModelsLabel = security.escapeHtml(i18n.t('plugins.modal.clonePlugin.cloneModels'));
    const cloneModelsDescription = security.escapeHtml(i18n.t('plugins.modal.clonePlugin.cloneModelsDesc'));
    const customNameLabel = security.escapeHtml(i18n.t('plugins.modal.clonePlugin.customName'));
    const customNameDescription = security.escapeHtml(i18n.t('plugins.modal.clonePlugin.customNameDesc'));

    return toTrustedUiHtml(`
                    <div class="plugin-info-item plugin-clone-summary">
                        <div class="plugin-info-content">
                            <div class="plugin-info-name">
                                <span id="${modalUiId(modalId, 'info-led')}" class="status-indicator plugin-info-led"></span>
                                <span data-tooltip="${security.escapeHtml(displayName)}">${security.escapeHtml(displayName)}</span>
                            </div>
                            <div class="plugin-info-details">
                                <span class="plugin-info-version">${versionHtml}</span>
                                <span class="plugin-info-author">${authorHtml}</span>
                            </div>
                            <div class="plugin-info-details">
                                <span class="plugin-info-status">${statusHtml}</span>
                            </div>
                        </div>
                        <div class="plugin-clone-controls">
                            <div class="plugin-clone-item">
                                <div class="plugin-clone-item-label">
                                    <span class="plugin-clone-item-title">${cloneModelsLabel}</span>
                                    <span class="plugin-clone-item-description">${cloneModelsDescription}</span>
                                </div>
                                <label class="toggle-switch">
                                    <input type="checkbox" id="${modalUiId(modalId, 'models-toggle')}">
                                    <span class="slider"></span>
                                </label>
                            </div>
                            <div class="plugin-clone-item">
                                <div class="plugin-clone-item-label">
                                    <span class="plugin-clone-item-title">${customNameLabel}</span>
                                    <span class="plugin-clone-item-description">${customNameDescription}</span>
                                </div>
                                <label class="toggle-switch">
                                    <input type="checkbox" id="${modalUiId(modalId, 'custom-name-toggle')}">
                                    <span class="slider"></span>
                                </label>
                            </div>
                        </div>
                    </div>`);
};

export { renderClonePluginInfoMarkup };
