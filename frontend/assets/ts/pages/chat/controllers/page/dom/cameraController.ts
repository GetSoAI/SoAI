/* SoAI - Chat page camera controller [frontend/assets/ts/pages/chat/controllers/page/dom/cameraController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type CameraInputActionSupportHost = PageDomOwnerHost;

const setCameraButtonEnabledMode = (button: HTMLButtonElement): void => {
    button.setAttribute('aria-disabled', 'false');
    button.setAttribute('data-toggle-disabled', 'false');
    button.removeAttribute('tabindex');
    const baseLabel = i18n.t('chat.input.openCamera');
    setTooltipText(button, baseLabel);
    button.setAttribute('aria-label', baseLabel);
};

const syncCameraInputActionSupport = (host: CameraInputActionSupportHost): void => {
    const cameraButtons = host.pageDom.query('.camera-btn');
    for (const candidate of cameraButtons) {
        if (!(candidate instanceof HTMLButtonElement)) {
            continue;
        }
        setCameraButtonEnabledMode(candidate);
    }
};

export { syncCameraInputActionSupport };
