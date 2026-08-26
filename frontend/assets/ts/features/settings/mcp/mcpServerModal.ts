/* SoAI - MCP server add/edit modal lifecycle [frontend/assets/ts/features/settings/mcp/mcpServerModal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createFormChangeSurfaceTracker } from '@core/forms/formChangeSurfaceTracker.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpServer } from '@core/mcp/contracts.ts';
import { attachBeforeCloseConfirmationGuard } from '@core/modals/closeGuard.ts';
import { createModalElementResolver } from '@core/modals/modalElementResolver.ts';
import { requireModalPresenter, type ModalDefinition } from '@core/modals/modalPresenter.ts';
import type { ModalOpenOptions } from '@core/modals/types.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL } from '@core/save/public.ts';
import { SETTINGS_MCP_SERVER_MODAL_ID } from '@features/settings/mcp/constants.ts';
import { resolveMcpServerModalElements } from '@features/settings/mcp/dom.ts';
import { performMcpServerModalSave } from '@features/settings/mcp/effects.ts';
import { syncMcpFormDefaultsToCurrent } from '@features/settings/mcp/mcpFormDefaultsSyncController.ts';
import { hasMcpServerFormPendingChanges, isMcpServerFormPendingChangesValid } from '@features/settings/mcp/mcpServerFormPendingController.ts';
import type { McpServerFormHost } from '@features/settings/mcp/mcpServerFormSnapshot.ts';
import { clearMcpServerModalSummary, setMcpServerModalFormValues, setMcpServerModalSummary, syncMcpServerModalFormState, type McpServerModalMode } from '@features/settings/mcp/mcpServerModalUiController.ts';
import type { McpServersHost } from '@features/settings/mcp/types.ts';
import { createMcpServerModalElement } from '@features/settings/mcp/view.ts';

const MODAL_ID = SETTINGS_MCP_SERVER_MODAL_ID;

const MCP_SERVER_MODAL_DRAFT_ID = '__mcp_server_modal_draft__';

type McpServerModalOpenOptions = {
    mode: McpServerModalMode;
    server: McpServer | null;
    revealManualOauthClient: boolean;
    reload: () => Promise<boolean>;
};

const validateMcpServerModalOpenOptions = (options: McpServerModalOpenOptions): void => {
    if (options.mode === 'create' && options.server !== null) {
        throw new Error('MCP server create mode must not receive an existing server');
    }
    if (options.mode === 'edit' && options.server === null) {
        throw new Error('MCP server edit mode requires an existing server');
    }
};

const mcpServerModalDefinition: ModalDefinition = {
    id: MODAL_ID,
    layout: 'xl',
    initialFocusSelector: modalUiSelector(MODAL_ID, 'name-input'),
    createElement: (_options: ModalOpenOptions): HTMLElement => createMcpServerModalElement(MODAL_ID)
};

const openMcpServerModal = async (host: McpServersHost, options: McpServerModalOpenOptions): Promise<void> => {
    validateMcpServerModalOpenOptions(options);
    const presenter = requireModalPresenter();
    if (presenter.isOpen(MODAL_ID)) {
        presenter.close(MODAL_ID, { force: true, reason: 'replace', restoreFocus: false });
    }
    const modal = presenter.requireElement(MODAL_ID);

    const abortController = new AbortController();
    const formHost: McpServerFormHost = {
        pageDom: host.view.pageDom,
        formRoot: modal,
        resolver: createModalElementResolver(modal, 'MCP server modal'),
        warnAndFocus: host.view.warnAndFocus
    };
    const elements = resolveMcpServerModalElements(host.view.pageDom, modal, MODAL_ID);
    const changeSurfaces = createFormChangeSurfaceTracker(modal);
    let server: McpServer | null = options.server;
    let mode: McpServerModalMode = options.mode;
    let revealManualOauthClient = options.revealManualOauthClient;
    let sessionClosed = false;

    const syncView = (): void => {
        revealManualOauthClient = revealManualOauthClient || !elements.oauthManualSection.hidden;
        elements.title.textContent = mode === 'edit' ? i18n.t('settings.mcp.servers.editTitle') : i18n.t('settings.mcp.servers.addTitle');
        syncMcpServerModalFormState({
            mode,
            transportSelect: elements.transportSelect,
            authSelect: elements.authSelect,
            apiKeyItem: elements.apiKeyItem,
            oauthManualSection: elements.oauthManualSection,
            oauthClientIdInput: elements.oauthClientIdInput,
            enabledItem: elements.enabledItem,
            enabledToggle: elements.enabledToggle,
            saveButton: elements.saveButton,
            revealManualOauthClient
        });
        revealManualOauthClient = revealManualOauthClient || !elements.oauthManualSection.hidden;
    };

    const syncEditSession = (nextMode: McpServerModalMode, nextServer: McpServer | null): void => {
        if (nextMode === 'edit' && nextServer === null) {
            throw new Error('MCP server edit session requires an existing server');
        }
        mode = nextMode;
        server = nextServer;
        host.editing.setMcpServerEditId(nextMode === 'edit' && nextServer ? nextServer.id : MCP_SERVER_MODAL_DRAFT_ID);
        host.editing.setMcpServerEditBaseline(nextServer);
        syncView();
    };

    const clearEditSession = (): void => {
        host.editing.setMcpServerEditId(null);
        host.editing.setMcpServerEditBaseline(null);
    };

    const closeModal = (): void => {
        presenter.close(MODAL_ID, { reason: 'confirm' });
    };

    const syncPendingState = (): void => {
        syncMcpFormDefaultsToCurrent(modal, { modalId: MODAL_ID });
        changeSurfaces.captureBaseline();
    };

    const confirmUnsavedChanges = async (): Promise<boolean> => await showUnsavedChangesConfirmation();
    const hasChanges = (): boolean => hasMcpServerFormPendingChanges(formHost, MODAL_ID);
    const isValid = (): boolean => isMcpServerFormPendingChangesValid(formHost, MODAL_ID, server?.authType ?? null);

    setMcpServerModalFormValues(elements, server);
    syncEditSession(mode, server);
    syncPendingState();

    const save = createSaveController({
        headerContextId: MODAL_ID,
        headerPriority: SAVE_HEADER_PRIORITY_MODAL,
        requestContextLabel: 'MCP server modal save',
        units: [{ id: 'mcp-server', hasChanges, isValid, save: async () => await runSaveFlow() }]
    });

    const removeCloseGuard = attachBeforeCloseConfirmationGuard({
        modal,
        presenter,
        modalId: MODAL_ID,
        shouldConfirmClose: hasChanges,
        confirmClose: confirmUnsavedChanges
    });

    elements.transportSelect.addEventListener(
        'change',
        () => {
            clearMcpServerModalSummary(elements.summary);
            syncView();
            changeSurfaces.sync();
            save.notifyChanged();
        },
        { signal: abortController.signal }
    );

    elements.authSelect.addEventListener(
        'change',
        () => {
            clearMcpServerModalSummary(elements.summary);
            syncView();
            changeSurfaces.sync();
            save.notifyChanged();
        },
        { signal: abortController.signal }
    );

    const performSave = async (): Promise<void> => {
        const result = await performMcpServerModalSave(
            {
                host,
                modalId: MODAL_ID,
                mode,
                server,
                reload: options.reload,
                formHost,
                summary: elements.summary,
                oauthManualSection: elements.oauthManualSection,
                oauthClientIdInput: elements.oauthClientIdInput
            },
            { reloadAfterSave: true }
        );
        if (sessionClosed) {
            return;
        }
        if (!result.persistedServer) {
            return;
        }

        syncEditSession(result.finalMode, result.persistedServer);
        syncPendingState();
        if (result.shouldClose) {
            closeModal();
        }
    };

    const runSaveFlow = async (): Promise<void> => {
        if (sessionClosed) {
            return;
        }
        try {
            clearMcpServerModalSummary(elements.summary);
            await host.execution.runWithBoundary('settings:mcpServerModalSave', async () => {
                await performSave();
            });
        } catch (error) {
            if (sessionClosed) {
                return;
            }
            const runtimeError = ensureError(error);
            errorHandler.warn('SettingsPage', 'MCP server modal save failed', runtimeError);
            const message = i18n.t('settings.mcp.notifications.serverSaveFailed');
            host.execution.feedback.show(message, 'error');
            setMcpServerModalSummary(elements.summary, message);
        }
    };

    const handleModalChanged = (): void => {
        changeSurfaces.sync();
        save.notifyChanged();
    };
    modal.addEventListener('input', handleModalChanged, { signal: abortController.signal });
    modal.addEventListener('change', handleModalChanged, { signal: abortController.signal });
    save.attach({ resolveSaveButtons: () => [elements.saveButton], busyRoots: [modal], autoNotifyRoot: modal });

    modal.addEventListener(
        'core.modal.close',
        () => {
            sessionClosed = true;
            removeCloseGuard();
            changeSurfaces.clear();
            save.dispose();
            clearEditSession();
            abortController.abort();
        },
        { signal: abortController.signal }
    );

    presenter.open(MODAL_ID, { force: true });
};

export { MCP_SERVER_MODAL_DRAFT_ID, mcpServerModalDefinition, openMcpServerModal };
