/* SoAI - Easter egg modal definition [frontend/assets/ts/features/about/modals/easterEggModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBranding } from '@core/branding/public.ts';
import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';

const EASTER_EGG_MODAL_ID = 'about-easter-egg-modal';

const easterEggModalDefinition: ModalDefinition = {
    id: EASTER_EGG_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: '.easter-egg-scene',
    createElement: (_options: ModalOpenOptions): HTMLElement => {
        const modalId = EASTER_EGG_MODAL_ID;
        const closeLabel = i18n.t('about.easterEgg.close');
        const interactHint = i18n.t('about.easterEgg.interactHint');
        const title = i18n.t('about.logoAlt');
        const header = renderStandardModalHeader({
            modalId,
            title,
            description: '',
            closeLabel,
            closeAttributes: { 'data-action': 'close' }
        });
        const body = renderModalBody(
            uiHtml`<div class="easter-egg-scene" tabindex="0" role="button" aria-label="${uiAttr(interactHint)}" data-tooltip="" data-modal-localize="aria-label">
            <div class="easter-egg-aurora"></div>
            <div class="easter-egg-starfield"></div>
            <div class="easter-egg-glow"></div>
            <canvas class="easter-egg-particles"></canvas>
            <div class="easter-egg-orb" data-phase="idle">
                <div class="orb-halo"></div>
                <div class="orb-shine"></div>
                <div class="orb-inner">
                    <img src="" alt="" class="orb-logo" data-logo-type="small" aria-hidden="true" decoding="async" />
                </div>
            </div>
        </div>`,
            { className: 'modal-body--no-padding modal-body--relative' }
        );
        const footer = renderModalFooter(renderModalFooterCloseButton({ modalId, text: closeLabel }));
        const element = createModalElement({
            id: modalId,
            contentClassName: 'easter-egg-content',
            rootAttributes: { 'data-page-scope': 'about' },
            header,
            body,
            footer
        });
        const logo = dom.resolve('.orb-logo', element);
        if (logo) {
            getBranding().updateLogoElement(logo, 'small');
        }
        return element;
    }
};

const ABOUT_MODAL_DEFINITIONS: readonly ModalDefinition[] = Object.freeze([easterEggModalDefinition]);

export { ABOUT_MODAL_DEFINITIONS };
export { EASTER_EGG_MODAL_ID };
