/* SoAI - Updates page system markup builder [frontend/assets/ts/pages/updates/controllers/UpdatesSystemMarkupBuilder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { UPDATES_ACTION_OPEN_PLUGINS } from '@pages/updates/actions.ts';
import { securityApi, renderLabelAttributes, toTrustedHtml, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { NormalizedUpdatePayload } from '@pages/updates/types.ts';

const buildVersionBlocks = (currentVersion: string, latestVersion: string, currentLabel: string, latestLabel: string, sanitizeHtml: (value: string) => string): string => `<div class="update-summary-grid"><div class="version-block"><span class="version-label">${sanitizeHtml(currentLabel)}</span><span class="version-value">${sanitizeHtml(currentVersion)}</span></div><div class="version-block"><span class="version-label">${sanitizeHtml(latestLabel)}</span><span class="version-value">${sanitizeHtml(latestVersion)}</span></div></div>`;

const buildBackendUpdatesMarkup = (plugins: readonly PluginRecord[]): TrustedHtml => {
    const unknown = i18n.t('common.unknown');
    const label = i18n.t('updates.backend.viewPlugins');
    return toTrustedUiHtml(plugins.map((plugin) => `<div class="update-summary-card"><div class="update-summary-header"><h2 class="update-summary-title" dir="auto">${securityApi.escapeHtml(plugin.displayName || plugin.name || unknown)}</h2><span class="ui-status-badge status-blue">${i18n.t('plugins.modal.manageBackend.update_available')}</span></div>${buildVersionBlocks(plugin.backendUpdate?.currentVersion || unknown, plugin.backendUpdate?.latestVersion || unknown, i18n.t('plugins.modal.manageBackend.current_version'), i18n.t('plugins.modal.manageBackend.newVersion'), securityApi.escapeHtml)}<div class="update-actions update-actions--end"><button class="ui-button ui-variant-primary" data-action="${UPDATES_ACTION_OPEN_PLUGINS}" type="button" ${renderLabelAttributes(label)}>${label}</button></div></div>`).join(''));
};

const buildUpdatesSummaryMarkup = (dependencies: { update: NormalizedUpdatePayload; savedLabel?: string | undefined; unknownLabel: string; updatesAvailableLabel: string; upToDateLabel: string; sectionTitle: string; currentVersionLabel: string; latestVersionLabel: string; publishedLabel: string; releaseLinkLabel: string; installActionLabel: string; installActionAriaLabel: string; sanitizeHtml: (value: string) => string; sanitizeAttribute: (value: string) => string; sanitizeUrl: (value: string, options: { allowRelative: boolean; allowDataImage: boolean; allowBlob: boolean }) => string | null; getIconSync: (name: IconName, options?: Record<string, JsonValue>) => TrustedHtml; iconOptions: Readonly<Record<string, JsonValue>> }): TrustedHtml => {
    const update = dependencies.update;
    const currentVersion = update.currentVersion || dependencies.unknownLabel;
    const latestVersion = update.latestVersion || dependencies.unknownLabel;
    const badge = dependencies.savedLabel ? `<span class="ui-status-badge status-grey">${dependencies.savedLabel}</span>` : update.updateAvailable ? `<span class="ui-status-badge status-orange">${dependencies.updatesAvailableLabel}</span>` : `<span class="ui-status-badge up-to-date">${dependencies.upToDateLabel}</span>`;

    const metadata: string[] = [];
    const published = formatReleaseDate(update.publishedAt);
    if (published) {
        metadata.push(`<div class="metadata-item"><span class="metadata-label">${dependencies.publishedLabel}</span><span class="metadata-value">${dependencies.sanitizeHtml(published)}</span></div>`);
    }
    if (update.releaseUrl) {
        const releaseUrl = dependencies.sanitizeUrl(update.releaseUrl, {
            allowRelative: false,
            allowDataImage: false,
            allowBlob: false
        });
        if (releaseUrl) {
            const icon = dependencies.getIconSync('external-link', dependencies.iconOptions);
            metadata.push(`<div class="metadata-item"><a class="metadata-link" href="${dependencies.sanitizeAttribute(releaseUrl)}" target="_blank" rel="noopener noreferrer">${icon.html}<span>${dependencies.releaseLinkLabel}</span></a></div>`);
        }
    }

    const actionHtml = update.updateAvailable ? `<div class="update-actions"><button class="ui-button ui-variant-accent" id="installUpdateBtn" data-action="updates.install" type="button" aria-label="${dependencies.installActionAriaLabel}" data-tooltip="${dependencies.installActionAriaLabel}">${dependencies.installActionLabel}</button></div>` : '';

    return toTrustedUiHtml(`<div class="update-summary-card"><div class="update-summary-header"><h2 class="update-summary-title">${dependencies.sectionTitle}</h2>${badge}</div>${buildVersionBlocks(currentVersion, latestVersion, dependencies.currentVersionLabel, dependencies.latestVersionLabel, dependencies.sanitizeHtml)}${actionHtml}${metadata.length ? `<div class="update-metadata">${metadata.join('')}</div>` : ''}</div>`);
};

const buildUpdatesReleaseNotesMarkup = (dependencies: { update: NormalizedUpdatePayload; sanitizeHtml: (value: string) => string; renderMarkdown: (value: string) => TrustedHtml; partialLabel: string }): { html: TrustedHtml; hasNotes: boolean } => {
    const update = dependencies.update;
    const entries = update.releaseHistory.length > 0 ? update.releaseHistory : update.releaseNotes.trim() ? [{ version: update.latestVersion, body: update.releaseNotes, publishedAt: update.publishedAt }] : [];
    if (entries.length === 0 && update.releaseHistoryComplete) {
        return { html: EMPTY_UI_HTML, hasNotes: false };
    }
    const sections = entries.map((entry) => `<section class="release-notes-entry"><h4>${dependencies.sanitizeHtml(entry.version)}</h4><div class="release-notes-entry-body">${dependencies.renderMarkdown(entry.body).html}</div></section>`);
    if (!update.releaseHistoryComplete) {
        sections.push(`<p class="release-notes-partial">${dependencies.sanitizeHtml(dependencies.partialLabel)}</p>`);
    }
    return {
        html: toTrustedHtml(sections.join('')),
        hasNotes: true
    };
};

const formatReleaseDate = (value: string): string => {
    if (!value) {
        return '';
    }
    return formatDateTime(value, false);
};

export { buildBackendUpdatesMarkup, buildUpdatesReleaseNotesMarkup, buildUpdatesSummaryMarkup };
