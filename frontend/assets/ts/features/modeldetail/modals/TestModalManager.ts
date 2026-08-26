/* SoAI - Model test modal manager [frontend/assets/ts/features/modeldetail/modals/TestModalManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { MODEL_DETAIL_TEST_MODAL_ID } from '@features/modeldetail/modals/constants.ts';
import { TEST_BUTTON_TOKENS } from '@features/modeldetail/modals/testmodalmanager/constants.ts';
import { ensureLogStream, runModelTestStream, teardownLogStream, updatePluginStatusDisplay } from '@features/modeldetail/modals/testmodalmanager/effects.ts';
import type { TestModalRuntimeContext } from '@features/modeldetail/modals/testmodalmanager/internalContracts.ts';
import { clearRequestDetails, updateRequestDetails } from '@features/modeldetail/modals/testmodalmanager/requestDetails.ts';
import { clearElapsedTimer, createInitialState, refreshElapsedDisplay, resetSession, setElapsedSpinnerVisible, setElapsedVisible, updateElapsedDisplay, updateResultMessage } from '@features/modeldetail/modals/testmodalmanager/state.ts';
import { appendFinalLogEntry, clearLogs, copyLogs, hideLogs, toggleLogsCollapse, updateToggleLogsButton } from '@features/modeldetail/modals/testmodalmanager/view.ts';
import type { TestModalManagerHost, TestModalManagerOptions, TestModalNotificationType, TestModalRequestStatus, TestModalState, TestModalStreamRequest, TestRunMode } from '@features/modeldetail/modals/TestModalManagerTypes.ts';

class TestModalManager {
    readonly modalId = MODEL_DETAIL_TEST_MODAL_ID;
    protected state: TestModalState;
    protected host: TestModalManagerHost;
    #testRunSequence = 0;

    constructor({ host }: TestModalManagerOptions) {
        if (!host) {
            throw new Error('TestModalManager requires a host');
        }
        this.host = host;
        this.state = createInitialState();
    }

    #getRuntimeContext(): TestModalRuntimeContext {
        return {
            host: this.host,
            state: this.state,
            modalId: this.modalId,
            modalRoot: this.host.model.modalPresenter.requireElement(this.modalId)
        };
    }

    #resolveModelIdForRequest(): string | null {
        const model = this.host.model.getModel();
        if (isObject(model)) {
            const universalId = model['universalId'];
            if (isString(universalId) && universalId.trim()) {
                return universalId.trim();
            }
            const id = model['id'];
            if (isString(id) && id.trim()) {
                return id.trim();
            }
        }
        const hostModelId = this.host.model.modelId;
        return isString(hostModelId) && hostModelId.trim() ? hostModelId.trim() : null;
    }

    #setTestButtonsDisabled(disabled: boolean): void {
        const modalRoot = this.host.model.modalPresenter.requireElement(this.modalId);
        TEST_BUTTON_TOKENS.forEach((token): void => {
            this.host.view.updateProperty(this.host.view.optionalUI(modalUiSelector(this.modalId, token), modalRoot), 'disabled', disabled);
        });
    }

    #notify(message: string, type: TestModalNotificationType = 'info'): void {
        this.host.view.showNotification(message, type);
    }

    toggleLogsCollapse(): void {
        toggleLogsCollapse(this.#getRuntimeContext());
    }

    copyLogs(): void {
        copyLogs(this.#getRuntimeContext());
    }

    teardownLogStream(): void {
        teardownLogStream(this.#getRuntimeContext());
    }

    updatePluginStatusDisplay(): void {
        const context = this.#getRuntimeContext();
        updatePluginStatusDisplay(context, (message: string): void => {
            updateResultMessage(context, message);
        });
    }

    resetModal(): void {
        this.#testRunSequence += 1;
        const context = this.#getRuntimeContext();
        resetSession(context);
        clearLogs(context);
        context.state.currentRequest = null;
        clearRequestDetails(context);
        updateResultMessage(context, i18n.t('modelDetail.modal.test.ready'));
        updateElapsedDisplay(context, 0);
        setElapsedVisible(context, false);
        setElapsedSpinnerVisible(context, false);
        hideLogs(context);
        teardownLogStream(context);
        context.state.logsCollapseController = null;
        this.updatePluginStatusDisplay();
    }

    openTestModal(): void {
        const context = this.#getRuntimeContext();
        if (!this.#resolveModelIdForRequest()) {
            this.#notify(i18n.t('modelDetail.notifications.testModelNotReady'), 'warning');
            return;
        }

        if (!this.state.active) {
            resetSession(context);
            clearLogs(context);
            hideLogs(context);
        }

        const title = this.host.view.optionalUI(modalUiSelector(this.modalId, 'title'), context.modalRoot);
        if (title) {
            const displayName = this.host.model.getModelDisplayName() || this.host.model.getModelSourceModelId() || this.host.model.modelId || i18n.t('modelDetail.modal.test.unknownModel');
            this.host.view.updateText(
                title,
                i18n.t('modelDetail.modal.test.title', {
                    model: displayName
                })
            );
        }

        this.updatePluginStatusDisplay();
        updateResultMessage(context, i18n.t('modelDetail.modal.test.ready'));
        this.host.model.modalPresenter.open(this.modalId);
    }

    async startTest(mode: TestRunMode): Promise<void> {
        return this.host.workflow.runWithBoundary('testModalManager:startTest', async (): Promise<void> => {
            await this.#startTestImpl(mode);
        });
    }

    async #startTestImpl(mode: TestRunMode): Promise<void> {
        const context = this.#getRuntimeContext();
        const runSequence = ++this.#testRunSequence;
        const resolvedModelId = this.#resolveModelIdForRequest();
        if (!resolvedModelId) {
            this.#notify(i18n.t('modelDetail.notifications.testModelNotReady'), 'warning');
            return;
        }

        resetSession(context);
        clearLogs(context);
        hideLogs(context);

        context.state.mode = mode;
        context.state.active = true;
        updateToggleLogsButton(context);
        context.state.logStartedAt = Date.now();

        const prompt = mode === 'short' ? i18n.t('modelDetail.modal.test.prompts.short') : i18n.t('modelDetail.modal.test.prompts.long');
        const modelLabel = this.host.model.getModelDisplayName() || this.host.model.getModelSourceModelId() || resolvedModelId;
        context.state.currentRequest = {
            id: `${resolvedModelId}:${context.state.logStartedAt}:${mode}`,
            mode,
            prompt,
            modelId: resolvedModelId,
            modelLabel,
            startedAt: context.state.logStartedAt,
            completedAt: null,
            status: 'running',
            response: ''
        };

        updateRequestDetails(context);
        setElapsedVisible(context, true);
        setElapsedSpinnerVisible(context, true);
        ensureLogStream(context);

        context.state.elapsedStartTime = Date.now();
        refreshElapsedDisplay(context);
        clearElapsedTimer(context);
        context.state.elapsedTimerId = this.host.view.setTimer(
            (): void => {
                refreshElapsedDisplay(context);
            },
            250,
            { repeat: true }
        );

        this.#setTestButtonsDisabled(true);
        const runningMessage = mode === 'short' ? i18n.t('modelDetail.modal.test.runningShort') : i18n.t('modelDetail.modal.test.runningLong');
        updateResultMessage(context, runningMessage);

        const request: TestModalStreamRequest = {
            model: resolvedModelId,
            messages: [{ role: 'user', content: prompt }],
            stream: true
        };

        const controller = new AbortController();
        context.state.abortController = controller;
        let requestWasCancelled = false;

        try {
            await runModelTestStream(context, request, controller.signal, runSequence, () => this.#testRunSequence);
        } catch (error) {
            if (runSequence !== this.#testRunSequence) {
                return;
            }

            const runtimeError = ensureError(error);
            if (controller.signal.aborted) {
                requestWasCancelled = true;
                updateResultMessage(context, i18n.t('modelDetail.modal.test.cancelled'));
            } else {
                errorHandler.error('TestModalManager', 'Model test stream failed', runtimeError);
                context.state.errorMessage = i18n.t('modelDetail.modal.test.errorGeneric');
                updateResultMessage(context, context.state.errorMessage);
            }
        } finally {
            if (runSequence !== this.#testRunSequence) {
                if (context.state.abortController === controller) {
                    context.state.abortController = null;
                }
                return;
            }

            context.state.completed = true;
            context.state.active = false;
            context.state.abortController = null;
            refreshElapsedDisplay(context);
            clearElapsedTimer(context);
            setElapsedSpinnerVisible(context, false);
            teardownLogStream(context);
            this.#setTestButtonsDisabled(false);

            const isSuccessful = !requestWasCancelled && !context.state.hasPluginError && !context.state.errorMessage;
            const finalStatus: TestModalRequestStatus = isSuccessful ? 'success' : requestWasCancelled ? 'cancelled' : 'error';
            const finalMessage = (() => {
                if (isSuccessful) return i18n.t('modelDetail.modal.test.success');
                if (requestWasCancelled) return i18n.t('modelDetail.modal.test.cancelled');
                if (context.state.errorMessage) return context.state.errorMessage;
                if (context.state.hasPluginError) return i18n.t('modelDetail.modal.test.errorPlugin');
                return i18n.t('modelDetail.modal.test.errorGeneric');
            })();

            updateResultMessage(context, finalMessage);
            if (context.state.currentRequest) {
                context.state.currentRequest.status = finalStatus;
                context.state.currentRequest.completedAt = Date.now();
            }

            appendFinalLogEntry(context, finalStatus, finalMessage);
            this.host.view.showNotification(finalMessage, isSuccessful ? 'success' : requestWasCancelled ? 'info' : 'error');
            updateRequestDetails(context);
            updateToggleLogsButton(context);
        }
    }
}

export { TestModalManager };
