/* SoAI - Password-change modal flow management for core.dialogs [frontend/assets/ts/core/ui/modals/dialogs/passwordChangeFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { resolvePasswordChangeDom, type PasswordChangeDom } from '@core/ui/modals/dialogs/passwordChangeDom.ts';
import type { PasswordChangeModalOptions, PasswordChangeValues } from '@core/ui/modals/dialogs/types.ts';
import { attachPendingOperationCloseGuard } from '@core/modals/closeGuard.ts';
import { createMutationRequestId } from '@core/mutations/mutationIdentity.ts';

interface PasswordChangeFlowApi {
    show: (request: PasswordChangeModalOptions) => Promise<boolean>;
}

const PASSWORD_MAX_LENGTH = 1024;
const PASSWORD_MIN_LENGTH = 8;

const setError = (elements: PasswordChangeDom, message: string | null): void => {
    elements.errorElement.hidden = !message;
    elements.errorElement.textContent = message ?? '';
};

const setPending = (elements: PasswordChangeDom, pending: boolean): void => {
    elements.submitButton.disabled = pending;
    elements.cancelButton.disabled = pending;
    elements.currentInput.disabled = pending;
    elements.newInput.disabled = pending;
    elements.confirmInput.disabled = pending;
};

const validate = (elements: PasswordChangeDom, request: PasswordChangeModalOptions): HTMLInputElement | null => {
    if (!elements.currentInput.value) {
        setError(elements, request.validationMessages.currentRequired);
        return elements.currentInput;
    }
    if (!elements.newInput.value) {
        setError(elements, request.validationMessages.newRequired);
        return elements.newInput;
    }
    if (elements.currentInput.value.length > PASSWORD_MAX_LENGTH || elements.newInput.value.length > PASSWORD_MAX_LENGTH) {
        setError(elements, request.validationMessages.tooLong);
        return elements.newInput;
    }
    if (elements.newInput.value.length < PASSWORD_MIN_LENGTH) {
        setError(elements, request.validationMessages.tooShort);
        return elements.newInput;
    }
    if (elements.confirmInput.value !== elements.newInput.value) {
        setError(elements, request.validationMessages.confirmMismatch);
        return elements.confirmInput;
    }
    setError(elements, null);
    return null;
};

const readValues = (elements: PasswordChangeDom, operationId: string): PasswordChangeValues => ({
    operationId,
    currentPassword: elements.currentInput.value,
    newPassword: elements.newInput.value
});

const createPasswordChangeFlow = (dependencies: { modalId: string }): PasswordChangeFlowApi => {
    const show = async (request: PasswordChangeModalOptions): Promise<boolean> => {
        const presenter = requireModalPresenter();
        return await runModalSession<boolean>({
            presenter,
            modalId: dependencies.modalId,
            onAlreadyOpen: 'replace',
            initialResult: false,
            initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
                const elements = resolvePasswordChangeDom(modal, dependencies.modalId);
                elements.titleElement.textContent = request.title;
                elements.descriptionElement.textContent = request.message;
                elements.descriptionElement.classList.toggle('u-hidden', request.message.trim().length <= 0);
                elements.currentLabel.textContent = request.fieldLabels.current;
                elements.newLabel.textContent = request.fieldLabels.new;
                elements.confirmLabel.textContent = request.fieldLabels.confirm;
                elements.currentInput.value = '';
                elements.newInput.value = '';
                elements.confirmInput.value = '';
                elements.cancelButton.textContent = i18n.t('common.cancel');
                elements.submitButton.textContent = request.submitText ?? i18n.t('common.save');
                setError(elements, null);
                let submitPending = false;
                let operationId: string | null = null;
                const detachCloseGuard = attachPendingOperationCloseGuard({ modal, isPending: () => submitPending });
                const applyPending = (pending: boolean): void => {
                    submitPending = pending;
                    setPending(elements, pending);
                };
                applyPending(false);

                const handleCancel = (event: Event): void => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (!submitPending) close('cancel');
                };

                const handleInput = (): void => {
                    setError(elements, null);
                };

                const submit = async (event: Event): Promise<void> => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (submitPending) {
                        return;
                    }
                    const invalidInput = validate(elements, request);
                    if (invalidInput) {
                        invalidInput.focus({ preventScroll: true });
                        return;
                    }
                    applyPending(true);
                    operationId = operationId ?? createMutationRequestId();
                    try {
                        const failure = await request.onSubmit(readValues(elements, operationId));
                        if (failure !== null) {
                            if (!failure.retainOperationId) operationId = null;
                            setError(elements, failure.message);
                            elements.currentInput.focus({ preventScroll: true });
                            return;
                        }
                        setResult(true);
                        close('confirm', { force: true });
                    } catch (error) {
                        const ensuredError = ensureError(error);
                        errorHandler.warn('PasswordChangeFlow', 'Password change submission failed unexpectedly', ensuredError);
                        setError(elements, request.validationMessages.updateFailed);
                    } finally {
                        applyPending(false);
                    }
                };

                elements.cancelButton.addEventListener('click', handleCancel, { signal });
                elements.submitButton.addEventListener('click', submit, { signal });
                elements.currentInput.addEventListener('input', handleInput, { signal });
                elements.newInput.addEventListener('input', handleInput, { signal });
                elements.confirmInput.addEventListener('input', handleInput, { signal });
                modal.addEventListener(
                    'keydown',
                    (event: Event): void => {
                        if (!(event instanceof KeyboardEvent) || event.key !== 'Enter' || event.repeat || event.isComposing) {
                            return;
                        }
                        if (event.target !== elements.currentInput && event.target !== elements.newInput && event.target !== elements.confirmInput) return;
                        terminateHandledPromise(submit(event));
                    },
                    { signal }
                );
                return {
                    dispose: (): void => {
                        detachCloseGuard();
                        elements.currentInput.value = '';
                        elements.newInput.value = '';
                        elements.confirmInput.value = '';
                        operationId = null;
                        setError(elements, null);
                    }
                };
            }
        });
    };
    return { show };
};

export { createPasswordChangeFlow };
export type { PasswordChangeFlowApi };
