/* SoAI - Settings feature label modal [frontend/assets/ts/features/settings/tokenflow/labelModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { readTrimmedInputValue } from '@core/dom/formValues.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { requireButtonElement, requireInputElement } from '@core/dom/typedElements.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalFooterActionButton, renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { renderModalBody, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { renderRequiredFieldLabel } from '@core/ui/forms/requiredMarker.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { bindModalEnterSubmit, buildSettingsTokenModalDefinition, createSettingsTokenModalElement, runSettingsTokenModalSession } from '@features/settings/tokenflow/modalScaffold.ts';
import type { SettingsTokenLabelModalConfig } from '@features/settings/tokenflow/types.ts';

const renderLabelInputMarkup = (config: SettingsTokenLabelModalConfig): TrustedHtml => {
    const placeholderMarkup = config.placeholder ? uiHtml` placeholder="${uiAttr(config.placeholder)}"` : uiHtml``;
    return uiHtml`
        <input type="text" id="${uiAttr(modalUiId(config.modalId, 'input'))}" class="form-input" data-modal-localize="aria-label placeholder" aria-label="${uiAttr(config.text.message)}" spellcheck="false" autocapitalize="off" autocomplete="off"${placeholderMarkup}>
    `;
};

const createSettingsTokenLabelModalElement = (config: SettingsTokenLabelModalConfig): HTMLElement => {
    const labelMarkup = config.required ? renderRequiredFieldLabel(config.text.message) : uiText(config.text.message);
    return createSettingsTokenModalElement({
        modalId: config.modalId,
        title: renderStandardModalHeader({
            modalId: config.modalId,
            title: config.text.title
        }),
        body: renderModalBody(
            uiHtml`
                <div class="confirmation-body">
                    <div class="confirmation-icon" aria-hidden="true">${getIconSync('key-modal', { size: 28 })}</div>
                    <div class="confirmation-message" data-modal-localize="text">${labelMarkup}</div>
                    <div class="confirmation-description" data-modal-localize="text">${config.text.description}</div>
                </div>
                <div class="form-group settings-token-flow-modal__field" data-modal-localize="text">${renderLabelInputMarkup(config)}</div>
            `,
            { className: 'prompt-modal-content' }
        ),
        footer: renderSplitModalFooter({
            left: renderModalFooterCloseButton({ modalId: config.modalId, text: i18n.t('common.cancel') }),
            right: toTrustedUiHtml(
                renderModalFooterActionButton({
                    id: modalUiId(config.modalId, 'next'),
                    text: i18n.t('common.next')
                }).html
            )
        })
    });
};

const createSettingsTokenLabelModalDefinition = (modalId: string, configFactory: () => SettingsTokenLabelModalConfig) =>
    buildSettingsTokenModalDefinition({
        modalId,
        initialFocusSelector: modalUiSelector(modalId, 'input'),
        configFactory,
        createElement: createSettingsTokenLabelModalElement
    });

const showSettingsTokenLabelModal = async (config: SettingsTokenLabelModalConfig, defaultValue: string): Promise<string | null> => {
    return await runSettingsTokenModalSession<string | null>({
        modalId: config.modalId,
        initialResult: null,
        initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
            const resolver = createModalElementResolver(modal, config.contextLabel);
            const inputElement = requireInputElement(resolver, modalUiSelector(config.modalId, 'input'), `${config.contextLabel} input`, modal);
            const nextButton = requireButtonElement(resolver, modalUiSelector(config.modalId, 'next'), `${config.contextLabel} next button`, modal);

            inputElement.value = defaultValue;
            const syncPlaceholder = (): void => {
                if (config.placeholder) return;
                const placeholder = inputElement.getAttribute('aria-label');
                if (placeholder === null) throw new Error('Token label input requires a localized label');
                inputElement.placeholder = placeholder;
            };
            syncPlaceholder();

            const syncNextButtonState = (): void => {
                setControlDisabledState(nextButton, config.required && readTrimmedInputValue(inputElement).length === 0);
            };

            const submit = (event: Event): void => {
                event.preventDefault();
                event.stopPropagation();
                const normalizedLabel = readTrimmedInputValue(inputElement);
                if (config.required && !normalizedLabel) {
                    syncNextButtonState();
                    return;
                }
                setResult(normalizedLabel);
                close('next');
            };

            syncNextButtonState();
            bindEventGroup(
                [
                    { target: modal, type: 'core.modal.localize', listener: syncPlaceholder },
                    { target: nextButton, type: 'click', listener: submit },
                    { target: inputElement, type: 'input', listener: syncNextButtonState }
                ],
                signal
            );
            bindModalEnterSubmit(inputElement, submit, signal);

            return { dispose: () => void 0 };
        }
    });
};

export { createSettingsTokenLabelModalDefinition, showSettingsTokenLabelModal };
