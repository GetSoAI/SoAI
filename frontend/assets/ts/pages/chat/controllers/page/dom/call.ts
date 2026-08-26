/* SoAI - Chat page call [frontend/assets/ts/pages/chat/controllers/page/dom/call.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type CallButtonHost = PageDomOwnerHost;

const updateCallButtonState = (host: CallButtonHost, active: boolean): void => {
    const title = active ? i18n.t('chat.input.voiceCallEnd') : i18n.t('chat.input.voiceCallStart');
    for (const button of host.pageDom.query('.call-btn')) {
        if (!(button instanceof HTMLElement)) {
            continue;
        }
        host.pageDom.toggleClass(button, 'is-active', active);
        setTooltipText(button, title);
        button.setAttribute('aria-label', title);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
    }
};

export { updateCallButtonState };
