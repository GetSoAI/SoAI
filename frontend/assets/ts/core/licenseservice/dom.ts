/* SoAI - Shared license service DOM contracts [frontend/assets/ts/core/licenseservice/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElementFromMarkup } from '@core/modals/scaffoldDom.ts';
import { renderModalBody, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import type { ModalButtonRefs, TextModalConfig, TextModalKey } from '@core/licenseservice/types.ts';

const resolveTitleText = (key: TextModalKey): string => {
    if (key === 'license') return i18n.t('about.licenseTitle');
    return i18n.t('about.creditsTitle');
};

const resolveCloseButtonAriaLabel = (key: TextModalKey): string => {
    if (key === 'license') return i18n.t('about.ariaLabels.closeLicense');
    return i18n.t('about.ariaLabels.closeCredits');
};

const resolveCopyButtonAriaLabel = (key: TextModalKey): string => {
    if (key === 'license') return i18n.t('about.ariaLabels.copyLicense');
    return i18n.t('about.ariaLabels.copyCredits');
};

const createTextModalMarkup = (config: TextModalConfig): TrustedHtml => {
    const modalId = config.id;
    const textId = modalUiId(modalId, 'text');
    const closeId = modalUiId(modalId, 'close');
    const copyId = modalUiId(modalId, 'copy');
    const closeButtonLabel = resolveCloseButtonAriaLabel(config.key);
    const copyButtonLabel = resolveCopyButtonAriaLabel(config.key);
    const header = renderStandardModalHeader({ modalId, title: resolveTitleText(config.key), description: config.key === 'license' ? i18n.t('common.modalDescriptions.license') : i18n.t('common.modalDescriptions.credits'), closeLabel: closeButtonLabel });
    const body = renderModalBody(uiHtml`<pre class="system-info-content u-stretch" id="${uiAttr(textId)}"></pre>`);
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, id: closeId, text: i18n.t('common.close'), ariaLabel: closeButtonLabel }),
        right: renderModalFooterActionButton({ id: copyId, text: i18n.t('common.copy'), ariaLabel: copyButtonLabel, variant: 'primary' })
    });
    return renderModalScaffoldMarkup({ id: modalId, className: config.className, contentClassName: 'license-modal-content', header, body, footer });
};

const createTextModalElement = (config: TextModalConfig): HTMLElement => {
    const modalMarkup = createTextModalMarkup(config);
    return createModalElementFromMarkup(config.id, modalMarkup);
};

const resolveTextModalButtons = (modalId: string, modalRoot: HTMLElement): ModalButtonRefs => {
    const closeButtonCandidate = dom.resolve(modalUiSelector(modalId, 'close'), modalRoot);
    const copyButtonCandidate = dom.resolve(modalUiSelector(modalId, 'copy'), modalRoot);
    return {
        closeButton: closeButtonCandidate instanceof HTMLButtonElement ? closeButtonCandidate : null,
        copyButton: copyButtonCandidate instanceof HTMLButtonElement ? copyButtonCandidate : null
    };
};

const resolveTextModalContent = (modalId: string, modalRoot: HTMLElement): HTMLElement | null => {
    const textElement = dom.resolve(modalUiSelector(modalId, 'text'), modalRoot);
    return textElement instanceof HTMLElement ? textElement : null;
};

export { createTextModalElement, resolveTextModalButtons, resolveTextModalContent };
