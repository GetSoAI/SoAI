/* SoAI - Settings feature expiry modal [frontend/assets/ts/features/settings/tokenflow/expiryModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { requireButtonElement } from '@core/dom/typedElements.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton } from '@core/modals/footerButtons.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { buildSettingsTokenModalDefinition, createSettingsTokenModalElement, runSettingsTokenModalSession } from '@features/settings/tokenflow/modalScaffold.ts';
import type { SettingsTokenExpiryChoice, SettingsTokenExpiryModalConfig } from '@features/settings/tokenflow/types.ts';

const createSettingsTokenExpiryModalElement = (config: SettingsTokenExpiryModalConfig): HTMLElement => {
    return createSettingsTokenModalElement({
        modalId: config.modalId,
        title: renderStandardModalHeader({
            modalId: config.modalId,
            title: config.title
        }),
        body: renderModalBody(uiHtml`<div class="confirmation-body"><div class="confirmation-icon" aria-hidden="true">${getIconSync('clock', { size: 22, strokeWidth: 1.7 })}</div><div class="confirmation-message">${config.help}</div><div class="confirmation-description">${config.description}</div></div>`, { className: 'prompt-modal-content' }),
        footer: renderSplitModalFooter({
            left: toTrustedUiHtml(
                renderModalFooterActionButton({
                    id: modalUiId(config.modalId, 'back'),
                    text: i18n.t('common.back')
                }).html
            ),
            right: toTrustedUiHtml(
                `${
                    renderModalFooterActionButton({
                        id: modalUiId(config.modalId, 'never'),
                        text: config.neverLabel,
                        variant: 'warning'
                    }).html
                }${
                    renderModalFooterActionButton({
                        id: modalUiId(config.modalId, '90days'),
                        text: config.ninetyDaysLabel,
                        variant: 'primary'
                    }).html
                }`
            )
        })
    });
};

const createSettingsTokenExpiryModalDefinition = (modalId: string, configFactory: () => SettingsTokenExpiryModalConfig) =>
    buildSettingsTokenModalDefinition({
        modalId,
        initialFocusSelector: modalUiSelector(modalId, '90days'),
        configFactory,
        createElement: createSettingsTokenExpiryModalElement
    });

const showSettingsTokenExpiryModal = async (config: SettingsTokenExpiryModalConfig): Promise<SettingsTokenExpiryChoice | null> => {
    return await runSettingsTokenModalSession<SettingsTokenExpiryChoice | null>({
        modalId: config.modalId,
        initialResult: null,
        initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
            const resolver = createModalElementResolver(modal, config.contextLabel);
            const backButton = requireButtonElement(resolver, modalUiSelector(config.modalId, 'back'), `${config.contextLabel} back button`, modal);
            const neverButton = requireButtonElement(resolver, modalUiSelector(config.modalId, 'never'), `${config.contextLabel} never button`, modal);
            const ninetyDaysButton = requireButtonElement(resolver, modalUiSelector(config.modalId, '90days'), `${config.contextLabel} 90 days button`, modal);

            const selectChoice =
                (choice: SettingsTokenExpiryChoice): ((event: Event) => void) =>
                (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    setResult(choice);
                    close(choice);
                };

            bindEventGroup(
                [
                    { target: backButton, type: 'click', listener: selectChoice('back') },
                    { target: neverButton, type: 'click', listener: selectChoice('never') },
                    { target: ninetyDaysButton, type: 'click', listener: selectChoice('90days') }
                ],
                signal
            );

            return { dispose: () => void 0 };
        }
    });
};

export { createSettingsTokenExpiryModalDefinition, showSettingsTokenExpiryModal };
