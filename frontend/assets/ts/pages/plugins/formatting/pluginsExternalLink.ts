/* SoAI - Plugins page external link [frontend/assets/ts/pages/plugins/formatting/pluginsExternalLink.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getWindowOpen } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { isElementNode } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

type PluginsExternalLinkHost = PageFeedbackOwnerHost;

const handlePluginsBackendWebsiteLinkClick = async (event: Event, host: PluginsExternalLinkHost): Promise<void> => {
    const target = isElementNode(event?.target) ? event.target : null;
    if (!target) throw new Error('Backend website click requires an event target element');
    const anchor = target.closest('a.plugin-backend-link');
    if (!anchor) throw new Error('Backend website link element not found');
    const url = anchor.getAttribute('data-backend-url') || anchor.getAttribute('href');
    if (!url) throw new Error('Backend website link is missing a URL');
    const confirmed = await requireDialogsService().showExternalLinkModal({ url });
    if (!confirmed) return;
    const sanitizedUrl = securityApi.sanitizeUrl(url, {
        allowRelative: false,
        allowDataImage: false,
        allowBlob: false
    });
    if (!sanitizedUrl) {
        errorHandler.error('PluginsPage', 'Backend website URL failed sanitization', { url });
        host.feedback.show(i18n.t('ui.errors.invalidUrl'), 'error', 6000);
        return;
    }
    getWindowOpen()(sanitizedUrl, '_blank', 'noopener,noreferrer');
};

export { handlePluginsBackendWebsiteLinkClick };
