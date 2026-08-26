/* SoAI - Updates page system markup builder [frontend/assets/ts/pages/updates/controllers/UpdatesSystemMarkupBuilder.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedHtml, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { formatDateTime } from '@core/primitives/dateTime.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { NormalizedUpdatePayload } from '@pages/updates/types.ts';

const buildUpdatesSummaryMarkup = (dependencies: { update: NormalizedUpdatePayload; unknownLabel: string; updatesAvailableLabel: string; upToDateLabel: string; sectionTitle: string; currentVersionLabel: string; latestVersionLabel: string; publishedLabel: string; releaseLinkLabel: string; installActionLabel: string; installActionAriaLabel: string; sanitizeHtml: (value: string) => string; sanitizeAttribute: (value: string) => string; sanitizeUrl: (value: string, options: { allowRelative: boolean; allowDataImage: boolean; allowBlob: boolean }) => string | null; getIconSync: (name: IconName, options?: Record<string, JsonValue>) => TrustedHtml; iconOptions: Readonly<Record<string, JsonValue>> }): TrustedHtml => {
    const update = dependencies.update;
    const currentVersion = update.currentVersion || dependencies.unknownLabel;
    const latestVersion = update.latestVersion || dependencies.unknownLabel;
    const badge = update.updateAvailable ? `<span class="ui-status-badge status-orange">${dependencies.updatesAvailableLabel}</span>` : `<span class="ui-status-badge up-to-date">${dependencies.upToDateLabel}</span>`;

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

    return toTrustedUiHtml(`<div class="update-summary-card"><div class="update-summary-header"><h2 class="update-summary-title">${dependencies.sectionTitle}</h2>${badge}</div><div class="update-summary-grid"><div class="version-block"><span class="version-label">${dependencies.currentVersionLabel}</span><span class="version-value">${dependencies.sanitizeHtml(currentVersion)}</span></div><div class="version-block"><span class="version-label">${dependencies.latestVersionLabel}</span><span class="version-value">${dependencies.sanitizeHtml(latestVersion)}</span></div></div>${actionHtml}${metadata.length ? `<div class="update-metadata">${metadata.join('')}</div>` : ''}</div>`);
};

const buildUpdatesReleaseNotesMarkup = (notes: string, sanitizeHtml: (value: string) => string): { html: TrustedHtml; hasNotes: boolean } => {
    const normalized = notes.trim();
    if (!normalized) {
        return { html: EMPTY_UI_HTML, hasNotes: false };
    }
    return {
        html: toTrustedHtml(sanitizeHtml(normalized).replaceAll('\n', '<br />')),
        hasNotes: true
    };
};

const formatReleaseDate = (value: string): string => {
    if (!value) {
        return '';
    }
    return formatDateTime(value, false);
};

export { buildUpdatesReleaseNotesMarkup, buildUpdatesSummaryMarkup };
