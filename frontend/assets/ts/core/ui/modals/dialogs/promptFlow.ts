/* SoAI - Prompt modal flow management for core.dialogs [frontend/assets/ts/core/ui/modals/dialogs/promptFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { resolvePromptDom } from '@core/ui/modals/dialogs/promptDom.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';

type PromptDomConfig = {
    title: string;
    message: string;
    placeholder: string;
    inputType: string;
    autocomplete: string;
    defaultValue: string;
    cancelText: string;
    confirmText: string;
};

interface PromptFlowApi {
    show: (request: PromptDomConfig & { validate?: ((value: string) => string | null) | undefined }) => Promise<string | null>;
}

const createPromptFlow = (dependencies: { modalId: string }): PromptFlowApi => {
    const show = async (request: PromptDomConfig & { validate?: ((value: string) => string | null) | undefined }): Promise<string | null> => {
        const presenter = requireModalPresenter();
        return await runModalSession<string | null>({
            presenter,
            modalId: dependencies.modalId,
            onAlreadyOpen: 'replace',
            initialResult: null,
            initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
                const domElements = resolvePromptDom(modal, dependencies.modalId);
                const { titleElement, messageElement, inputElement, cancelButton, confirmButton } = domElements;

                dom.setText(titleElement, request.title);
                dom.setText(messageElement, request.message);

                inputElement.value = request.defaultValue;
                inputElement.placeholder = request.placeholder;
                inputElement.type = request.inputType;
                inputElement.setAttribute('autocomplete', request.autocomplete);

                dom.setText(cancelButton, request.cancelText);
                cancelButton.disabled = false;

                dom.setText(confirmButton, request.confirmText);
                confirmButton.disabled = false;

                const validate = request.validate ?? null;

                const handleCancelClick = (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    close('cancel');
                };

                const tryConfirm = (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    const value = inputElement.value;
                    if (validate) {
                        const message = validate(value);
                        if (typeof message === 'string' && message.trim()) {
                            showNotification(message, 'warning', 4500);
                            inputElement.focus({ preventScroll: true });
                            return;
                        }
                    }
                    setResult(value);
                    close('confirm');
                };

                cancelButton.addEventListener('click', handleCancelClick, { signal });
                confirmButton.addEventListener('click', tryConfirm, { signal });
                inputElement.addEventListener(
                    'keydown',
                    (event: Event): void => {
                        if (!(event instanceof KeyboardEvent)) {
                            return;
                        }
                        if (event.key !== 'Enter') {
                            return;
                        }
                        tryConfirm(event);
                    },
                    { signal }
                );

                return { dispose: () => void 0 };
            }
        });
    };

    return { show };
};

export { createPromptFlow };
export type { PromptDomConfig, PromptFlowApi };
