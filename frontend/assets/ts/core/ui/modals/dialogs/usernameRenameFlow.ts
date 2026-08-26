/* SoAI - Username-rename modal flow [frontend/assets/ts/core/ui/modals/dialogs/usernameRenameFlow.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { attachPendingOperationCloseGuard } from '@core/modals/closeGuard.ts';
import { requireModalPresenter } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { createMutationRequestId } from '@core/mutations/mutationIdentity.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { isCanonicalUsernameInput } from '@core/users/username.ts';
import { resolveUsernameRenameDom, type UsernameRenameDom } from '@core/ui/modals/dialogs/usernameRenameDom.ts';
import type { UsernameRenameModalOptions, UsernameRenameValues } from '@core/ui/modals/dialogs/types.ts';

interface UsernameRenameFlowApi {
    show: (request: UsernameRenameModalOptions) => Promise<boolean>;
}

const setRenameError = (elements: UsernameRenameDom, message: string | null): void => {
    elements.errorElement.hidden = message === null;
    elements.errorElement.textContent = message ?? '';
};

const setRenamePending = (elements: UsernameRenameDom, pending: boolean): void => {
    elements.usernameInput.disabled = pending;
    elements.passwordInput.disabled = pending;
    elements.cancelButton.disabled = pending;
    elements.submitButton.disabled = pending;
};

const validateRename = (elements: UsernameRenameDom, request: UsernameRenameModalOptions): HTMLInputElement | null => {
    if (!isCanonicalUsernameInput(elements.usernameInput.value)) {
        setRenameError(elements, request.invalidUsername);
        return elements.usernameInput;
    }
    if (elements.usernameInput.value.toLowerCase() === request.currentUsername) {
        setRenameError(elements, request.unchangedUsername);
        return elements.usernameInput;
    }
    if (!elements.passwordInput.value) {
        setRenameError(elements, request.passwordRequired);
        return elements.passwordInput;
    }
    setRenameError(elements, null);
    return null;
};

const createUsernameRenameFlow = (dependencies: { modalId: string }): UsernameRenameFlowApi => ({
    show: async (request): Promise<boolean> => {
        const presenter = requireModalPresenter();
        return await runModalSession<boolean>({
            presenter,
            modalId: dependencies.modalId,
            onAlreadyOpen: 'replace',
            initialResult: false,
            initialize: ({ modal, signal, setResult, close }) => {
                const elements = resolveUsernameRenameDom(modal, dependencies.modalId);
                elements.titleElement.textContent = request.title;
                elements.descriptionElement.textContent = request.message;
                elements.usernameLabel.textContent = request.usernameLabel;
                elements.passwordLabel.textContent = request.passwordLabel;
                elements.submitButton.textContent = request.submitText;
                elements.usernameInput.value = request.currentUsername;
                elements.passwordInput.value = '';
                elements.usernameInput.focus({ preventScroll: true });
                elements.usernameInput.select();
                let pending = false;
                let operationId: string | null = null;
                const detachCloseGuard = attachPendingOperationCloseGuard({ modal, isPending: () => pending });
                const submit = async (event: Event): Promise<void> => {
                    event.preventDefault();
                    event.stopPropagation();
                    if (pending) return;
                    const invalid = validateRename(elements, request);
                    if (invalid) {
                        invalid.focus({ preventScroll: true });
                        return;
                    }
                    operationId = operationId ?? createMutationRequestId();
                    pending = true;
                    setRenamePending(elements, true);
                    const values: UsernameRenameValues = { operationId, newUsername: elements.usernameInput.value.toLowerCase(), currentPassword: elements.passwordInput.value };
                    try {
                        const failure = await request.onSubmit(values);
                        if (failure !== null) {
                            if (!failure.retainOperationId) operationId = null;
                            setRenameError(elements, failure.message);
                            return;
                        }
                        setResult(true);
                        close('confirm', { force: true });
                    } catch (error) {
                        errorHandler.warn('UsernameRenameFlow', 'Username rename submission failed unexpectedly', ensureError(error));
                        setRenameError(elements, request.updateFailed);
                    } finally {
                        pending = false;
                        setRenamePending(elements, false);
                    }
                };
                const submitFromClick = (event: Event): void => {
                    terminateHandledPromise(submit(event));
                };
                const clearError = (): void => {
                    setRenameError(elements, null);
                };
                elements.cancelButton.addEventListener(
                    'click',
                    (event) => {
                        event.preventDefault();
                        if (!pending) close('cancel');
                    },
                    { signal }
                );
                elements.submitButton.addEventListener('click', submitFromClick, { signal });
                elements.usernameInput.addEventListener('input', clearError, { signal });
                elements.passwordInput.addEventListener('input', clearError, { signal });
                modal.addEventListener(
                    'keydown',
                    (event) => {
                        if (!(event instanceof KeyboardEvent) || event.key !== 'Enter' || event.repeat || event.isComposing) return;
                        if (event.target !== elements.usernameInput && event.target !== elements.passwordInput) return;
                        terminateHandledPromise(submit(event));
                    },
                    { signal }
                );
                return {
                    dispose: (): void => {
                        detachCloseGuard();
                        elements.passwordInput.value = '';
                        elements.usernameInput.value = '';
                        operationId = null;
                        setRenameError(elements, null);
                    }
                };
            }
        });
    }
});

export { createUsernameRenameFlow };
export type { UsernameRenameFlowApi };
