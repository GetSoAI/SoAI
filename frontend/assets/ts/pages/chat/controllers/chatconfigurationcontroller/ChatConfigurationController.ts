/* SoAI - Chat configuration controller ownership [frontend/assets/ts/pages/chat/controllers/chatconfigurationcontroller/ChatConfigurationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_MODAL, type SaveController } from '@core/save/public.ts';
import type { ChatParameters, ConversationSettingsSavePlanInput } from '@features/chat/public.ts';
import { FieldStateTracker } from '@core/forms/fieldStateTracker.ts';
import { ConfigurationEditSessionStateManager, type EditableConfigurationSessionState } from '@pages/chat/controllers/chatconfigurationcontroller/ConfigurationEditSessionStateManager.ts';
import { cancelConfigurationEditState, commitConfigurationEditState, createConfigurationEditSession, hasPendingConfigurationParameterChanges } from '@pages/chat/controllers/chatconfigurationcontroller/effects.ts';
import { applyConfigurationCommitSideEffects, applyConfigurationParameterSideEffects, refreshConfigurationParameterUi, type ConfigurationProjectionEffect } from '@pages/chat/controllers/chatconfigurationcontroller/service.ts';
import type { ConfigurationControllerHost, ConfigurationControllerStateAccess, ConversationSettingsSavePlan } from '@pages/chat/controllers/chatconfigurationcontroller/types.ts';
import { ConfigurationOperationGate } from '@pages/chat/controllers/chatconfigurationcontroller/configurationOperationGateDomain.ts';
import { ConfigurationModelSelectionStateManager, type ConfigurationModelSnapshot } from '@pages/chat/controllers/chatconfigurationcontroller/ConfigurationModelSelectionStateManager.ts';
import { ChatModelControlController } from '@pages/chat/controllers/chatmodelcontrol/ChatModelControlController.ts';
import { resolveEffectiveModelsForChatModelControl } from '@pages/chat/controllers/chatmodelcontrol/chatModelControlStateManager.ts';
import { createConfigurationModelControl } from '@pages/chat/controllers/chatconfigurationcontroller/ConfigurationModelControlComposition.ts';
import { cloneChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { commitConversationCoreProjection, createChatConfigurationSaveUnits, haveConversationParameterChanges, normalizeConversationSettingsSavePlan } from '@pages/chat/controllers/chatconfigurationcontroller/chatConfigurationSavePlanDomain.ts';
import { haveConfigurationPreferenceChanges } from '@pages/chat/controllers/chatconfigurationcontroller/chatConfigurationPreferencePatchDomain.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { attachChatConfigurationSave } from '@pages/chat/controllers/chatconfigurationcontroller/chatConfigurationSaveBindingController.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isChatPresetModelParameterStateValid } from '@pages/chat/controllers/chatconfigurationcontroller/chatPresetModelValidationDomain.ts';
import { ChatConfigurationSaveOutcomeTracker } from '@pages/chat/controllers/chatconfigurationcontroller/chatConfigurationSaveOutcomeDomain.ts';
import { resolveRestoredDisabledParameterValues } from '@pages/chat/controllers/chatconfigurationcontroller/configurationDisabledParameterStateDomain.ts';

class ChatConfigurationController implements EditableConfigurationSessionState {
    #host: ConfigurationControllerHost;
    #state: ConfigurationControllerStateAccess;
    #isDestroyed = false;
    #activeTab: string = 'general';
    #settingsPlan: ConversationSettingsSavePlan = { conversation: null, knowledge: null, tools: null };
    #parameterChangeTracker: FieldStateTracker | null = null;
    readonly #save: SaveController;
    readonly #operationGate = new ConfigurationOperationGate();
    readonly #operationGateDisposer: () => void;
    readonly model: ConfigurationModelSelectionStateManager;
    readonly modelControl: ChatModelControlController;
    readonly #saveOutcome = new ChatConfigurationSaveOutcomeTracker();
    #pendingProjectionEffects: readonly ConfigurationProjectionEffect[] = [];

    editingParameters: ChatParameters | null = null;
    parameterEditBaseline: ChatParameters | null = null;
    pendingParameterChanges = false;
    constructor(options: { host: ConfigurationControllerHost; state: ConfigurationControllerStateAccess; headerActionContextId: string }) {
        this.#host = options.host;
        this.#state = options.state;
        this.model = new ConfigurationModelSelectionStateManager({
            root: options.host.root,
            getModels: () => this.#state.getModels(),
            getModelIndex: () => this.#state.getModelIndex(),
            hasModelCatalog: () => this.#state.hasModelCatalog(),
            isSelectionLocked: () => this.#host.modelControl.isSelectionLocked()
        });
        this.modelControl = createConfigurationModelControl({
            host: options.host.modelControl,
            root: options.host.root,
            state: options.state,
            model: this.model,
            onStateChange: this.recalculateConfigurationDirtyState
        });
        this.#save = createSaveController({
            headerContextId: options.headerActionContextId,
            headerPriority: SAVE_HEADER_PRIORITY_MODAL,
            requestContextLabel: 'Chat configuration save',
            admission: {
                canAcquire: () => this.#operationGate.canAcquire(),
                acquire: () => {
                    this.#saveOutcome.begin(this.parameterEditBaseline);
                    return this.#operationGate.acquire('save');
                }
            },
            units: createChatConfigurationSaveUnits({
                host: this.#host,
                hasWritableConversation: () => this.#state.hasWritableCurrentConversation(),
                parameters: () => this.editingParameters,
                model: () => this.model.workingModel(),
                comparisonModels: () => this.model.workingComparisonModels(),
                parametersDirty: () => this.pendingParameterChanges,
                conversationParametersDirty: () => haveConversationParameterChanges(this.editingParameters, this.parameterEditBaseline),
                modelDirty: () => this.model.isDirty(),
                preferencesDirty: () => haveConfigurationPreferenceChanges(this.editingParameters, this.parameterEditBaseline),
                projectionEffectsDirty: () => this.#pendingProjectionEffects.length > 0,
                coreValid: () => (this.#parameterChangeTracker?.isValid() ?? true) && this.model.isValid() && isChatPresetModelParameterStateValid(this.getWorkingParameters(), this.model.workingModel(), this.#state.getModelIndex()),
                settingsPlan: () => this.#settingsPlan,
                editSession: () => this.parameterEditBaseline,
                isEditSessionActive: (session) => session !== null && session === this.parameterEditBaseline,
                commitConversationCore: (parameters, models, parametersDirty, modelDirty) =>
                    commitConversationCoreProjection({
                        active: !this.#isDestroyed,
                        captured: parameters,
                        baseline: this.parameterEditBaseline,
                        parametersDirty,
                        models,
                        modelDirty,
                        state: this.#state,
                        modelController: this.model,
                        refresh: () => {
                            refreshConfigurationParameterUi(this.#state);
                            this.#recalculateConfigurationDirtyStateImmediate();
                        }
                    }),
                commitAllCore: async () => (this.#isDestroyed ? false : await this.commitConfigurationEdit()),
                retryProjectionEffects: async () => (this.#isDestroyed ? false : await this.#retryProjectionEffects()),
                stop: (error, unitId) => {
                    this.#saveOutcome.fail(unitId);
                    errorHandler.error('ChatConfigurationController', `Chat configuration ${unitId} save failed`, ensureError(error));
                    return { type: 'stop' };
                },
                invalidate: (unitId) => {
                    this.#saveOutcome.fail(unitId);
                    return false;
                },
                complete: (unitId) => this.#saveOutcome.complete(unitId)
            }),
            onSaveSettled: (outcome) => {
                if (this.#isDestroyed || !this.#saveOutcome.isCurrent(this.parameterEditBaseline)) return;
                const presentation = this.#saveOutcome.presentation(outcome);
                if (presentation) this.#host.feedback.show(presentation.message, presentation.type);
            }
        });
        this.#operationGateDisposer = this.#operationGate.subscribe(() => this.#save.notifyChanged());
    }

    dispose(): void {
        this.#isDestroyed = true;
        this.#operationGateDisposer();
        this.#save.dispose();
        this.#parameterChangeTracker?.clearAll();
        this.#parameterChangeTracker = null;
        this.editingParameters = null;
        this.parameterEditBaseline = null;
        this.modelControl.closeMenu();
        this.model.cancel();
    }

    hideHeaderSaveAction(): void {
        this.#save.attach({ resolveSaveButtons: () => [], enableHeaderAction: false, autoNotifyRoot: null });
    }
    operationGate(): ConfigurationOperationGate {
        return this.#operationGate;
    }
    hasPendingChanges(): boolean {
        return this.pendingParameterChanges || this.model.isDirty() || this.#pendingProjectionEffects.length > 0 || Object.values(this.#settingsPlan).some((action) => action?.hasChanges === true);
    }

    readonly getWorkingParameters = (): ChatParameters => (this.editingParameters ? this.editingParameters : this.#state.getParameters());
    getParameterBaseline(): ChatParameters | null {
        return this.parameterEditBaseline ? cloneChatParameters(this.parameterEditBaseline) : null;
    }
    canCommitPresetWorkingState(snapshot: ConfigurationModelSnapshot, parameters: ChatParameters): boolean {
        return this.model.canCommitSnapshot(snapshot) && isChatPresetModelParameterStateValid(parameters, snapshot.model, this.#state.getModelIndex());
    }
    canStagePresetModel(snapshot: ConfigurationModelSnapshot): boolean {
        return snapshot.model !== null && snapshot.selectable && !this.#host.modelControl.isSelectionLocked() && this.model.canCommitSnapshot(snapshot);
    }
    isParameterLocked(parameter: string): boolean {
        return this.#state.getParameterManager()?.isParameterLocked(parameter) ?? false;
    }
    commitPresetWorkingState(parameters: ChatParameters, model: ConfigurationModelSnapshot): void {
        if (!this.editingParameters) throw new Error('Chat configuration edit session is not active.');
        this.editingParameters = cloneChatParameters(parameters);
        this.model.commitSnapshot(model);
    }

    refreshPresetWorkingPresentation(): void {
        refreshConfigurationParameterUi(this.#state);
        this.modelControl.render();
        this.#recalculateConfigurationDirtyStateImmediate();
    }

    refreshModelControlPresentation(): void {
        this.model.refreshPresentation();
        this.modelControl.render();
        this.recalculateConfigurationDirtyState();
    }

    isEditingConfiguration(): boolean {
        return this.editingParameters !== null;
    }

    getEditingTextZoom(): number | null {
        const textZoom = this.editingParameters?.textZoom;
        return textZoom === undefined ? null : textZoom;
    }

    setEditingTextZoom(zoom: number): void {
        if (!this.editingParameters) throw new Error('Chat editing parameters are required to set editing text zoom');
        this.editingParameters.textZoom = zoom;
    }

    assignWorkingParameters(parameters: Partial<ChatParameters>): void {
        const target = this.isEditingConfiguration() ? this.editingParameters : cloneChatParameters(this.#state.getParameters());
        if (!target) {
            throw new Error('Chat preset assignment requires active parameter target');
        }
        for (const parameterKey of Object.keys(parameters)) {
            target[parameterKey] = parameters[parameterKey];
        }
        if (!this.isEditingConfiguration()) this.#state.setParameters(target);
    }

    beginConfigurationEdit(): void {
        if (this.isEditingConfiguration()) {
            return;
        }
        ConfigurationEditSessionStateManager.applyConfigurationEditSessionState(this, createConfigurationEditSession(this.#host, this.#state), (tracker) => {
            this.#parameterChangeTracker = tracker;
        });
        this.model.begin(resolveEffectiveModelsForChatModelControl({ conversation: this.#host.modelControl.getCurrentConversation(), fallbackModelId: this.#state.getCurrentModel() }));
        this.modelControl.render();
        if (!this.#isDestroyed) attachChatConfigurationSave(this.#save, this.#host);
        refreshConfigurationParameterUi(this.#state);
        this.updateConfigurationSaveState();
    }

    cancelConfigurationEdit(): void {
        if (!this.isEditingConfiguration()) {
            this.updateConfigurationSaveState();
            return;
        }
        cancelConfigurationEditState({
            parameterChangeTracker: this.#parameterChangeTracker
        });
        ConfigurationEditSessionStateManager.clearConfigurationEditSessionState(this, (tracker) => {
            this.#parameterChangeTracker = tracker;
        });
        this.model.cancel();
        refreshConfigurationParameterUi(this.#state);
        this.updateConfigurationSaveState();
    }

    readonly commitConfigurationEdit = async (): Promise<boolean> => {
        if (this.model.isDirty()) this.#state.setCurrentModel(this.model.workingModel());
        const commitState = commitConfigurationEditState({
            stateAccess: this.#state,
            host: this.#host,
            editingParameters: this.editingParameters
        });
        if (commitState.committed) {
            this.model.rebase();
            this.#parameterChangeTracker?.clearAll();
            ConfigurationEditSessionStateManager.applyConfigurationEditSessionState(this, createConfigurationEditSession(this.#host, this.#state), (tracker) => {
                this.#parameterChangeTracker = tracker;
            });
            this.#pendingProjectionEffects = await applyConfigurationCommitSideEffects(
                commitState,
                {
                    stateAccess: this.#state,
                    host: this.#host
                },
                this.#pendingProjectionEffects
            );
        }
        this.updateConfigurationSaveState();
        return this.#pendingProjectionEffects.length > 0;
    };

    async #retryProjectionEffects(): Promise<boolean> {
        const emptyCommit = { committed: false, backendDefaultsChanged: false, richTextChanged: false, senderLabelChanged: false, inputActionsChanged: false, sendHotkeyChanged: false, toolsEnabledChanged: false, toolApprovalRequiredChanged: false, conversationListFiltersChanged: false };
        this.#pendingProjectionEffects = await applyConfigurationCommitSideEffects(emptyCommit, { stateAccess: this.#state, host: this.#host }, this.#pendingProjectionEffects, false);
        this.updateConfigurationSaveState();
        return this.#pendingProjectionEffects.length > 0;
    }

    updateParameterValue(parameter: string, value: JsonValue): void {
        const target = this.isEditingConfiguration() ? this.editingParameters : cloneChatParameters(this.#state.getParameters());
        if (target) {
            target[parameter] = value;
            if (!this.isEditingConfiguration()) this.#state.setParameters(target);
        }
        const restoredDisabledParameters = resolveRestoredDisabledParameterValues({ parameters: this.editingParameters, baseline: this.parameterEditBaseline, parameter, value });
        applyConfigurationParameterSideEffects(parameter, {
            isEditingConfiguration: () => this.isEditingConfiguration(),
            stateAccess: this.#state,
            host: this.#host,
            recalculateDirtyState: () => this.recalculateConfigurationDirtyState()
        });
        for (const restoredParameter of restoredDisabledParameters) {
            this.#parameterChangeTracker?.clear(restoredParameter);
        }
        if (restoredDisabledParameters.length > 0) {
            refreshConfigurationParameterUi(this.#state);
        }
    }

    setParameterValidity(parameter: string, valid: boolean): void {
        this.#parameterChangeTracker?.setInvalid(parameter, valid ? null : 'invalid');
        this.updateConfigurationSaveState();
    }

    readonly recalculateConfigurationDirtyState = (): void => {
        this.#parameterChangeTracker?.setInvalid('maxCompletionTokens', isChatPresetModelParameterStateValid(this.getWorkingParameters(), this.model.workingModel(), this.#state.getModelIndex()) ? null : 'invalid');
        this.#recalculateConfigurationDirtyStateImmediate();
    };

    #recalculateConfigurationDirtyStateImmediate(): void {
        if (!this.isEditingConfiguration()) {
            return;
        }
        this.pendingParameterChanges = hasPendingConfigurationParameterChanges(this.editingParameters, this.parameterEditBaseline);
        const parameterKeys = this.editingParameters ? Object.keys(this.editingParameters) : [];
        this.#parameterChangeTracker?.refresh(parameterKeys);
        this.updateConfigurationSaveState();
    }

    setActiveTab(tabId: string): void {
        this.#activeTab = tabId ? tabId : 'general';
        this.updateConfigurationSaveState();
    }

    getActiveTab(): string {
        return this.#activeTab;
    }

    updateConfigurationSaveState(): void {
        this.#save.notifyChanged();
    }

    setConversationSettingsSavePlan(plan: ConversationSettingsSavePlanInput | null): void {
        this.#settingsPlan = normalizeConversationSettingsSavePlan(plan);
        this.updateConfigurationSaveState();
    }

    saveConfiguration(): void {
        terminateHandledPromise(this.#save.requestSave());
    }
}

export type { ConfigurationControllerHost, ConfigurationControllerStateAccess };
export { ChatConfigurationController };
