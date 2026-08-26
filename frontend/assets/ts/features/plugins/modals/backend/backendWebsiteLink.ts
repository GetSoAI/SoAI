/* SoAI - Plugins feature backend website link [frontend/assets/ts/features/plugins/modals/backend/backendWebsiteLink.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { resolveHttpsWebsiteUrl } from '@core/security/public.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import type { BackendManagerSecurity } from '@features/plugins/modals/backend/backendTypes.ts';

const getBackendWebsiteUrl = (plugin: { websiteBackend?: string | null }): string | null => {
    const websiteBackend = plugin.websiteBackend;
    const rawUrl = (isString(websiteBackend) ? websiteBackend : '').trim();
    if (!rawUrl) return null;
    return resolveHttpsWebsiteUrl(rawUrl);
};

const buildBackendWebsiteLink = (id: string, url: string | null, security: BackendManagerSecurity): string => {
    if (!url) return '';
    if (!security || !isFunction(security.escapeAttribute) || !isFunction(security.escapeHtml)) {
        throw new Error('Backend website link requires a security module');
    }
    const safeId = security.escapeAttribute(id);
    const safeUrl = security.escapeAttribute(url);
    const icon = getIconSync('external-link', { size: 10, strokeWidth: 1.2 }).html;
    const label = security.escapeHtml(i18n.t('plugins.modal.installBackend.website_backend'));
    return `<div class="plugin-info-details plugin-info-link"><a id="${safeId}" class="plugin-backend-link" href="${safeUrl}" data-backend-url="${safeUrl}" rel="noopener noreferrer" target="_blank">${icon}<span class="plugin-backend-link-text">${label}</span></a></div>`;
};

export { getBackendWebsiteUrl, buildBackendWebsiteLink };
