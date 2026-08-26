/* SoAI - Messaging account editor modal session [frontend/assets/ts/features/settings/messaging/modal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { dom } from '@core/dom/dom.ts';
import { readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { openChatParameterEditorModal } from '@core/chat/parameters/parameterEditorModalSession.ts';
import { createChatParameterEditorProjection } from '@core/chat/parameters/parameterEditorState.ts';
import { createFormChangeSurfaceTracker } from '@core/forms/formChangeSurfaceTracker.ts';
import { setFieldSurfaceModified } from '@core/forms/fieldSurface.ts';
import { WorkspacePathDraft } from '@core/fileexplorerbrowser/workspacePathDraft.ts';
import { i18n } from '@core/i18n/index.ts';
import { McpFormController } from '@core/mcp/mcpFormController.ts';
import { haveMcpFormValuesChanged, normalizeMcpConfigValues, syncMcpToolChangeSurfaces } from '@core/mcp/toolChangeSurfaces.ts';
import { attachBeforeCloseConfirmationGuard, attachPendingOperationCloseGuard } from '@core/modals/closeGuard.ts';
import { createModalBusyState } from '@core/modals/modalBusyState.ts';
import { requireModalPresenter, type ModalDefinition } from '@core/modals/modalPresenter.ts';
import { runModalSession } from '@core/modals/modalSession.ts';
import { createModalElementFromMarkup } from '@core/modals/scaffoldDom.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL } from '@core/save/public.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { showUserError } from '@core/ui/notifications/notifications.ts';
import { MESSAGING_MODAL_ACTION_PARAMETERS, MESSAGING_MODAL_ACTION_WORKSPACE, SETTINGS_MESSAGING_ACCOUNT_MODAL_ID, SETTINGS_MESSAGING_PARAMETERS_MODAL_ID, isMessagingModalActionId } from '@features/settings/messaging/constants.ts';
import { applyMessagingModelChange, applyMessagingParameterEditorState, initializeMessagingEditor, readMessagingDraft, syncCredentialSections, syncSenderAccessState } from '@features/settings/messaging/modalFormState.ts';
import { createMessagingDraftProjection, validateMessagingDraft } from '@features/settings/messaging/modalDraft.ts';
import { buildMessagingPersistencePayload } from '@features/settings/messaging/modalPersistencePayload.ts';
import { resolveMessagingPersistenceError } from '@features/settings/messaging/modalPersistenceErrors.ts';
import { createMessagingValidationPresenter } from '@features/settings/messaging/modalValidation.ts';
import { createMessagingAccountModalElement, MESSAGING_MCP_ACTIONS, renderMessagingParametersModalMarkup } from '@features/settings/messaging/modalView.ts';
import { resolveMessagingModelOption } from '@features/settings/messaging/modelOptions.ts';
import type { MessagingAccountModalOptions, MessagingAccountModalResult } from '@features/settings/messaging/types.ts';

const messagingAccountModalDefinition: ModalDefinition = {
    id: SETTINGS_MESSAGING_ACCOUNT_MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(SETTINGS_MESSAGING_ACCOUNT_MODAL_ID, 'label'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createMessagingAccountModalElement(SETTINGS_MESSAGING_ACCOUNT_MODAL_ID)
};

const messagingParametersModalDefinition: ModalDefinition = {
    id: SETTINGS_MESSAGING_PARAMETERS_MODAL_ID,
    layout: 'lg',
    initialFocusSelector: modalUiSelector(SETTINGS_MESSAGING_PARAMETERS_MODAL_ID, 'system-prompt-input'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createModalElementFromMarkup(SETTINGS_MESSAGING_PARAMETERS_MODAL_ID, renderMessagingParametersModalMarkup())
};

const requireElement = <T extends HTMLElement>(modal: Element, token: string, expected: new (...parameters: never[]) => T): T => {
    const element = dom.resolve(modalUiSelector(SETTINGS_MESSAGING_ACCOUNT_MODAL_ID, token), modal);
    if (!(element instanceof expected)) throw new Error(`Messaging account modal element is missing: ${token}`);
    return element;
};

const setPersistenceError = (modal: HTMLElement, message: string | null): void => {
    const error = requireElement(modal, 'error', HTMLElement);
    error.textContent = message ?? '';
    error.hidden = message === null;
};

const openMessagingAccountModal = async (options: MessagingAccountModalOptions): Promise<MessagingAccountModalResult | null> =>
    await runModalSession<MessagingAccountModalResult | null>({
        presenter: requireModalPresenter(),
        modalId: SETTINGS_MESSAGING_ACCOUNT_MODAL_ID,
        onAlreadyOpen: 'replace',
        initialResult: null,
        initialize: ({ modal, signal, setResult, close }): { dispose: () => void } => {
            const form = requireElement(modal, 'form', HTMLFormElement);
            const saveButton = requireElement(modal, 'save-btn', HTMLButtonElement);
            const editorState = initializeMessagingEditor(modal, options);
            const parametersSummary = requireElement(modal, 'parameters-summary', HTMLInputElement);
            const initialParametersProjection = createChatParameterEditorProjection(editorState);
            const syncParametersSummary = (): void => {
                const projection = createChatParameterEditorProjection(editorState);
                parametersSummary.dataset['parametersProjection'] = projection;
                const custom = editorState.initiallyExplicitSettings || projection !== initialParametersProjection;
                parametersSummary.value = custom ? i18n.t('settings.messaging.editor.parameters.summaryCustom') : i18n.t('settings.messaging.editor.parameters.summaryDefault');
            };
            syncParametersSummary();
            const workspace = new WorkspacePathDraft();
            workspace.setValue(options.account?.modelSettings.workspacePath, options.workspaceBrowserAccess.currentWorkspacePath);
            requireElement(modal, 'workspace', HTMLInputElement).value = workspace.getSummary();
            const mcp = new McpFormController({
                root: modal,
                toolsList: requireElement(modal, 'mcp-tools-list', HTMLElement),
                toolsEmpty: requireElement(modal, 'mcp-tools-empty', HTMLElement),
                modalId: SETTINGS_MESSAGING_ACCOUNT_MODAL_ID,
                actions: MESSAGING_MCP_ACTIONS,
                toolModes: ['default', 'plan', 'execute'],
                initialToolMode: 'default',
                getIconSync
            });
            mcp.setCatalog(options.mcpCatalog);
            if (options.account?.modelSettings.mcp) mcp.setValues(options.account.modelSettings.mcp);
            else
                mcp.setValues({
                    defaultTools: [...options.mcpCatalog.defaultTools],
                    planTools: [...options.mcpCatalog.planTools],
                    executeTools: [...options.mcpCatalog.executeTools],
                    serverConfigs: {},
                    toolsEnabled: true,
                    toolApprovalRequired: true
                });

            const changeSurfaces = dom.resolveAll('.messaging-account-modal__group:not(.messaging-account-modal__mcp)', form).map((group) => createFormChangeSurfaceTracker(group));
            const normalizeCurrentMcp = () => normalizeMcpConfigValues({ ...mcp.readConfig(), knowledgeState: null });
            const baselineMcp = normalizeCurrentMcp();
            let baseline = createMessagingDraftProjection(readMessagingDraft(modal, options, editorState, mcp, workspace));
            let workspacePending = false;
            let parametersPending = false;
            let completed = false;
            const validation = createMessagingValidationPresenter(modal, options.mode);

            const currentDraft = () => readMessagingDraft(modal, options, editorState, mcp, workspace);
            const hasChanges = (): boolean => createMessagingDraftProjection(currentDraft()) !== baseline || haveMcpFormValuesChanged(normalizeCurrentMcp(), baselineMcp);
            const admission = () =>
                validateMessagingDraft(currentDraft(), {
                    requiredPlanTools: options.mcpCatalog.planTools,
                    requiredExecuteTools: options.mcpCatalog.executeTools,
                    models: options.models
                });
            const isValid = (): boolean => {
                const result = admission();
                return !workspacePending && !parametersPending && form.checkValidity() && result.complete && result.valid;
            };

            const editableControls = dom
                .resolveAll('input, select, textarea, button[data-modal-close]', modal)
                .filter((element): element is HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement | HTMLButtonElement => {
                    return element instanceof HTMLInputElement || element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement || element instanceof HTMLButtonElement;
                })
                .filter((element) => element !== saveButton);
            const busyState = createModalBusyState(modal, { controls: editableControls.map((element) => ({ element })) });

            const save = createSaveController({
                headerContextId: SETTINGS_MESSAGING_ACCOUNT_MODAL_ID,
                headerPriority: SAVE_HEADER_PRIORITY_MODAL,
                requestContextLabel: 'Messaging account modal save',
                units: [
                    {
                        id: 'messaging-account',
                        hasChanges,
                        isValid,
                        save: async (): Promise<void> => {
                            const payload = buildMessagingPersistencePayload(currentDraft(), options.account);
                            try {
                                const persisted = await options.persist(payload);
                                setResult(persisted);
                            } catch (error) {
                                const runtimeError = error instanceof Error ? error : new Error('Messaging persistence failed');
                                const publicMessage = resolveMessagingPersistenceError(runtimeError, currentDraft().platform);
                                setPersistenceError(modal, publicMessage);
                                showUserError(publicMessage);
                                throw runtimeError;
                            }
                        }
                    }
                ],
                onSaveComplete: (): void => {
                    completed = true;
                    baseline = createMessagingDraftProjection(currentDraft());
                    close('save');
                }
            });
            const syncChanged = (target: EventTarget | null = null): void => {
                setPersistenceError(modal, null);
                validation.touch(target);
                for (const changeSurface of changeSurfaces) changeSurface.sync();
                setFieldSurfaceModified(parametersSummary, createChatParameterEditorProjection(editorState) !== initialParametersProjection);
                syncMcpToolChangeSurfaces({
                    modalRoot: modal,
                    baseline: baselineMcp,
                    current: normalizeCurrentMcp(),
                    includeTopLevelSurfaces: true
                });
                validation.sync(admission().invalidFields);
                save.notifyChanged();
            };

            save.attach({
                resolveSaveButtons: () => [saveButton],
                enableHeaderAction: false,
                onBusyChange: (busy): void => {
                    busyState.setBusy(busy);
                }
            });
            for (const changeSurface of changeSurfaces) changeSurface.captureBaseline();
            const detachPendingGuard = attachPendingOperationCloseGuard({ modal, isPending: () => save.isSaving() || workspacePending || parametersPending });
            const detachDirtyGuard = attachBeforeCloseConfirmationGuard({
                modal,
                presenter: requireModalPresenter(),
                modalId: SETTINGS_MESSAGING_ACCOUNT_MODAL_ID,
                shouldConfirmClose: () => !completed && !save.isSaving() && !workspacePending && !parametersPending && hasChanges(),
                confirmClose: showUnsavedChangesConfirmation
            });

            bindDataActionListener({
                root: modal,
                eventType: 'click',
                signal,
                isAction: isMessagingModalActionId,
                preventDefault: 'always',
                mouseButton: 'primary',
                ignoreDisabled: true,
                onAction: ({ action }): void => {
                    if (workspacePending || parametersPending || save.isSaving()) return;
                    if (action === MESSAGING_MODAL_ACTION_PARAMETERS) {
                        terminateHandledPromise(
                            (async (): Promise<void> => {
                                parametersPending = true;
                                save.notifyChanged();
                                try {
                                    const selectedModel = resolveMessagingModelOption(options.models, readTrimmedSelectValue(requireElement(modal, 'model', HTMLSelectElement)));
                                    const edited = await openChatParameterEditorModal({
                                        presenter: requireModalPresenter(),
                                        modalId: SETTINGS_MESSAGING_PARAMETERS_MODAL_ID,
                                        initialState: editorState,
                                        includeSystemPromptLock: false,
                                        canApply: () => !signal.aborted && requireModalPresenter().isOpen(SETTINGS_MESSAGING_ACCOUNT_MODAL_ID),
                                        resolveModelDetailId: () => selectedModel?.detailUniversalId ?? null,
                                        supportedReasoningLevels: selectedModel?.supportedReasoningLevels ?? null
                                    });
                                    if (!edited || signal.aborted) return;
                                    applyMessagingParameterEditorState(editorState, edited);
                                    syncParametersSummary();
                                } finally {
                                    parametersPending = false;
                                    syncChanged(parametersSummary);
                                }
                            })()
                        );
                        return;
                    }
                    if (action !== MESSAGING_MODAL_ACTION_WORKSPACE) return;
                    terminateHandledPromise(
                        (async (): Promise<void> => {
                            workspacePending = true;
                            busyState.setBusy(true);
                            save.notifyChanged();
                            try {
                                const changed = await workspace.open({
                                    access: options.workspaceBrowserAccess,
                                    readOnly: false,
                                    canApply: () => !signal.aborted,
                                    strings: {
                                        title: i18n.t('chat.configuration.filesFolder.pickerTitle'),
                                        message: i18n.t('chat.configuration.filesFolder.pickerMessage'),
                                        chooseCurrent: i18n.t('common.save')
                                    }
                                });
                                if (changed) requireElement(modal, 'workspace', HTMLInputElement).value = workspace.getSummary();
                            } finally {
                                workspacePending = false;
                                busyState.setBusy(false);
                                syncChanged();
                            }
                        })()
                    );
                }
            });

            const handleFormEvent = (event: Event): void => {
                const platform = requireElement(modal, 'platform', HTMLSelectElement);
                const model = requireElement(modal, 'model', HTMLSelectElement);
                if (event.target === platform) syncCredentialSections(modal);
                if (event.target === model) applyMessagingModelChange(modal, options, editorState, mcp, workspace);
                if (event.target === requireElement(modal, 'accept-anyone', HTMLInputElement)) syncSenderAccessState(modal);
                syncChanged(event.target);
            };
            form.addEventListener('input', handleFormEvent, { signal });
            form.addEventListener('change', handleFormEvent, { signal });
            form.addEventListener(
                'submit',
                (event) => {
                    event.preventDefault();
                    terminateHandledPromise(save.requestSave());
                },
                { signal }
            );
            validation.sync(admission().invalidFields);
            isValid();
            save.notifyChanged();
            busyState.setBusy(save.isSaving());

            return {
                dispose: (): void => {
                    detachPendingGuard();
                    detachDirtyGuard();
                    save.dispose();
                    for (const changeSurface of changeSurfaces) changeSurface.clear();
                    mcp.destroy();
                }
            };
        }
    });

export { messagingAccountModalDefinition, messagingParametersModalDefinition, openMessagingAccountModal };
