/* SoAI - Shared modals header buttons [frontend/assets/ts/core/modals/headerButtons.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TrustedHtml } from '@core/security/public.ts';
import { dom } from '@core/dom/dom.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync, type IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE = 'data-modal-header-role';
const MODAL_HEADER_CLOSE_SELECTOR = '[data-modal-header-role="close"]';
const MODAL_HEADER_FULLSCREEN_SELECTOR = '[data-modal-header-role="fullscreen"]';
const MODAL_HEADER_ACTION_BUTTON_CLASS = 'modal-header-action-button';
const MODAL_HEADER_CLOSE_BUTTON_CLASS = 'modal-header-close-button';
const MODAL_HEADER_FULLSCREEN_BUTTON_CLASS = 'modal-header-fullscreen-button';

type ModalHeaderButtonRole = 'close' | 'fullscreen';

const buildModalHeaderButtonClassName = (role: ModalHeaderButtonRole): string => {
    const roleClassName = role === 'close' ? MODAL_HEADER_CLOSE_BUTTON_CLASS : MODAL_HEADER_FULLSCREEN_BUTTON_CLASS;
    const variantClassName = role === 'close' ? 'ui-round-button--modal-close' : 'ui-round-button--neutral';
    return `ui-round-button ui-round-button--inline ${MODAL_HEADER_ACTION_BUTTON_CLASS} ${roleClassName} ${variantClassName}`;
};

const renderModalHeaderButtonIcon = (iconName: IconName, options: IconOptions = { size: 14, strokeWidth: 1.5 }): TrustedHtml => {
    return renderIconSlot(getIconSync(iconName, options));
};

const createModalHeaderButtonElement = ({ role, label, modalId }: { role: ModalHeaderButtonRole; label: string; modalId: string }): HTMLButtonElement => {
    const iconName = role === 'close' ? 'close' : 'modal-expand';
    const button = document.createElement('button');
    button.className = buildModalHeaderButtonClassName(role);
    button.type = 'button';
    button.setAttribute('aria-label', label);
    setTooltipText(button, label);
    button.setAttribute(MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE, role);
    if (role === 'close') {
        button.setAttribute('data-modal-close', modalId);
    } else {
        button.setAttribute('data-modal-id', modalId);
    }
    dom.setHTML(button, renderModalHeaderButtonIcon(iconName), { escape: false });
    return button;
};

export { MODAL_HEADER_ACTION_BUTTON_CLASS, MODAL_HEADER_BUTTON_ROLE_ATTRIBUTE, MODAL_HEADER_CLOSE_BUTTON_CLASS, MODAL_HEADER_CLOSE_SELECTOR, MODAL_HEADER_FULLSCREEN_BUTTON_CLASS, MODAL_HEADER_FULLSCREEN_SELECTOR, buildModalHeaderButtonClassName, createModalHeaderButtonElement, renderModalHeaderButtonIcon };
