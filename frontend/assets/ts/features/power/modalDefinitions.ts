/* SoAI - Power mode modal definitions [frontend/assets/ts/features/power/modalDefinitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { requireRootHTMLElement, requireRootButton } from '@core/dom/typedElementResolver.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModalDefinition } from '@core/modals/modalPresenter.ts';
import { createModalElement } from '@core/modals/scaffoldDom.ts';
import { renderSplitModalFooter } from '@core/modals/scaffold.ts';
import { EMPTY_UI_HTML, joinUiHtml, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { buildPowerActionDefinitions } from '@features/power/actionDefinitions.ts';

const POWER_MODE_MODAL_ID = 'power-mode-modal';

const renderPowerGroup = (application: boolean): ReturnType<typeof uiHtml> => {
    const title = application ? i18n.t('power.groups.application') : i18n.t('power.groups.system');
    const actions = buildPowerActionDefinitions().filter((action) => action.key.endsWith('Application') === application);
    return uiHtml`<section class="power-mode-group" data-power-group="${uiAttr(application ? 'application' : 'system')}" aria-label="${uiAttr(title)}" data-modal-localize="aria-label"><div class="power-mode-actions">${joinUiHtml(actions.map((action) => uiHtml`<div class="power-mode-action${action.key === 'shutdownApplication' ? ' power-action--application-shutdown' : ''}" data-power-action="${uiAttr(action.key)}"><button type="button" class="ui-icon-button power-mode-button" data-action="${uiAttr(action.key)}"${renderLabelAttributes(action.title)}>${getIconSync(action.icon, { size: 32 })}</button><span class="power-mode-label" aria-hidden="true" data-modal-localize="text">${uiText(action.title)}</span></div>`))}</div></section>`;
};

const refreshPowerModeText = (modal: HTMLElement): void => {
    dom.setText(requireRootHTMLElement(modal, '#power-mode-title', 'Power title'), i18n.t('pages.power.title'));
    const back = requireRootButton(modal, '#power-mode-back', 'Power Back');
    back.setAttribute('aria-label', i18n.t('common.back'));
    setTooltipText(back, i18n.t('common.back'));
    const cancel = requireRootButton(modal, '[data-power-mode-cancel]', 'Power Cancel');
    dom.setText(cancel, i18n.t('common.cancel'));
    cancel.setAttribute('aria-label', i18n.t('common.cancel'));
    setTooltipText(cancel, i18n.t('common.cancel'));
    const groups: readonly ('application' | 'system')[] = ['application', 'system'];
    for (const group of groups) {
        const section = requireRootHTMLElement(modal, `[data-power-group="${group}"]`, 'Power group');
        const title = group === 'application' ? i18n.t('power.groups.application') : i18n.t('power.groups.system');
        section.setAttribute('aria-label', title);
    }
    for (const action of buildPowerActionDefinitions()) {
        const button = requireRootButton(modal, `[data-action="${action.key}"]`, 'Power action');
        button.setAttribute('aria-label', action.title);
        setTooltipText(button, action.title);
        dom.setText(requireRootHTMLElement(modal, `[data-power-action="${action.key}"] > .power-mode-label`, 'Power label'), action.title);
    }
};

const POWER_MODAL_DEFINITIONS: readonly ModalDefinition[] = [
    {
        id: POWER_MODE_MODAL_ID,
        presentation: 'viewport',
        layout: 'md',
        initialFocusSelector: '[data-power-initial-focus]',
        createElement: () =>
            createModalElement({
                id: POWER_MODE_MODAL_ID,
                className: 'power-mode',
                rootAttributes: { 'data-page-scope': 'power' },
                labelledBy: 'power-mode-title',
                header: EMPTY_UI_HTML,
                body: uiHtml`<div class="power-mode-surface" data-presence-atomic></div><div class="power-mode-header" data-presence-suspended><button id="power-mode-back" class="ui-icon-button hamburger-menu" type="button" data-modal-close="${uiAttr(POWER_MODE_MODAL_ID)}" ${renderLabelAttributes(i18n.t('common.back'))}><span class="power-mode-navigation-icon" aria-hidden="true"><span class="power-mode-navigation-glyph power-mode-menu-glyph">${getIconSync('menu', { size: 22 })}</span><span class="power-mode-navigation-glyph power-mode-back-glyph">${getIconSync('arrow-left', { size: 22 })}</span></span></button></div><div class="power-mode-scroll"><div class="power-mode-chooser" data-presence-atomic><h1 id="power-mode-title" class="visually-hidden" data-modal-localize="text">${uiText(i18n.t('pages.power.title'))}</h1><div class="power-mode-groups">${renderPowerGroup(true)}${renderPowerGroup(false)}</div>${renderSplitModalFooter({ left: uiHtml`<button type="button" class="ui-button" data-power-mode-cancel data-modal-close="${uiAttr(POWER_MODE_MODAL_ID)}" ${renderLabelAttributes(i18n.t('common.cancel'))} data-modal-localize="text">${uiText(i18n.t('common.cancel'))}</button>`, right: uiHtml`<span id="power-mode-restart-notice" class="ui-status-badge warning power-mode-restart-notice u-hidden" role="status" data-presence-visual-only>${getIconSync('restart', { size: 14 })}<span class="power-mode-restart-notice-text"></span></span>` })}</div></div>`
            })
    }
];

export { POWER_MODE_MODAL_ID, POWER_MODAL_DEFINITIONS, refreshPowerModeText };
