/* SoAI - Settings feature secret modal [frontend/assets/ts/features/settings/tokenflow/secretModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { copyTextToClipboard, resolveClipboardService } from '@core/ui/modals/dialogs/clipboardCopy.ts';
import { parseNotificationType } from '@core/ui/notifications/notificationTypeParsing.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { buildSettingsTokenModalDefinition, createSettingsTokenModalElement, runSettingsTokenModalSession } from '@features/settings/tokenflow/modalScaffold.ts';
import type { SettingsTokenSecretModalConfig } from '@features/settings/tokenflow/types.ts';

const createSettingsTokenSecretModalElement = (config: SettingsTokenSecretModalConfig): HTMLElement => {
    return createSettingsTokenModalElement({
        modalId: config.modalId,
        className: 'settings-token-flow-modal settings-token-flow-modal--secret',
        title: renderStandardModalHeader({
            modalId: config.modalId,
            title: config.title
        }),
        body: renderModalBody(uiHtml`<div class="confirmation-body"><div class="confirmation-icon" aria-hidden="true">${getIconSync('copy', { size: 25, strokeWidth: 1.6 })}</div><div class="confirmation-message">${config.title}</div><div class="confirmation-description">${config.message} <span class="settings-token-flow-modal__description-emphasis">${config.messageEmphasis}</span></div></div><div class="settings-token-secret-display form-row-split manual-path-row settings-token-flow-modal__field"><div class="form-col-main"><input type="text" id="${uiAttr(modalUiId(config.modalId, 'value'))}" class="form-input settings-token-secret-field" aria-label="${uiAttr(config.title)}" readonly spellcheck="false" autocapitalize="off" autocomplete="off"></div></div>`, { className: 'prompt-modal-content' }),
        footer: renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId: config.modalId, text: i18n.t('common.close') }),
            right: toTrustedUiHtml(
                renderModalFooterActionButton({
                    id: modalUiId(config.modalId, 'copy'),
                    text: config.copyLabel,
                    variant: 'primary'
                }).html
            )
        })
    });
};

const createSettingsTokenSecretModalDefinition = (modalId: string, configFactory: () => SettingsTokenSecretModalConfig) =>
    buildSettingsTokenModalDefinition({
        modalId,
        initialFocusSelector: modalUiSelector(modalId, 'value'),
        configFactory,
        createElement: createSettingsTokenSecretModalElement
    });

const showSettingsTokenSecretModal = async (config: SettingsTokenSecretModalConfig, secret: string): Promise<void> => {
    await runSettingsTokenModalSession<void>({
        modalId: config.modalId,
        initialResult: undefined,
        initialize: ({ modal, signal }): { dispose: () => void } => {
            const resolver = createModalElementResolver(modal, config.contextLabel);
            const valueElement = requireInputElement(resolver, modalUiSelector(config.modalId, 'value'), `${config.contextLabel} value`, modal);
            const copyButton = requireButtonElement(resolver, modalUiSelector(config.modalId, 'copy'), `${config.contextLabel} copy button`, modal);
            const clipboardService = resolveClipboardService();
            const disabled = !clipboardService || clipboardService.isSupported() !== true;

            valueElement.value = secret;
            setControlDisabledState(copyButton, disabled);
            copyButton.classList.toggle('ui-variant-primary', true);
            setTooltipText(copyButton, disabled ? i18n.t('common.clipboard.copyUnavailable') : config.copyLabel);

            copyButton.addEventListener(
                'click',
                (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    terminateHandledPromise(
                        copyTextToClipboard(secret, {
                            notify: (messageValue: string, type: string): void => {
                                void showNotification(messageValue, parseNotificationType(type));
                            },
                            successMessage: i18n.t('common.clipboard.copied'),
                            errorMessage: i18n.t('common.clipboard.copyFailed'),
                            unavailableMessage: i18n.t('common.clipboard.copyUnavailable')
                        })
                    );
                },
                { signal }
            );

            return { dispose: () => void 0 };
        }
    });
};

export { createSettingsTokenSecretModalDefinition, showSettingsTokenSecretModal };
