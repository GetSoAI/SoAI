/* SoAI - Hardware page GPU control manager [frontend/assets/ts/pages/hardware/controllers/gpucontrol/GpuControlManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GpuSlotsBuilderResult } from '@core/types/streamTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { createSaveController, SAVE_HEADER_PRIORITY_PAGE, type SaveController } from '@core/save/public.ts';
import { isElementNode, isNullOrUndefined } from '@core/typeGuards.ts';
import { resetGpuSettings } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/effects.ts';
import { handleGpuBootToggle } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/payloads.ts';
import { handleGpuApplyClick, handleGpuSlotClick } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/service.ts';
import type { ControlContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolactions/types.ts';
import { GPU_CONTROL_TYPES, GPU_PREVIEW_KEY_MAP, GPU_SETTING_KEYS, GPU_SLIDER_CONFIG } from '@pages/hardware/controllers/gpucontrol/gpuControlConfig.ts';
import { getSliderElements, getSliderSnapshot, markGpuStateHydrated, resetGpuUiControls, setSliderToAuto, setSliderToManual, updateSliderAutoState } from '@pages/hardware/controllers/gpucontrol/gpuControlDomControls.ts';
import { refreshGpuApplyState } from '@pages/hardware/controllers/gpucontrol/gpuControlApplyStateRefreshController.ts';
import { resolveGpuPrimaryAction } from '@pages/hardware/controllers/gpucontrol/gpuControlPrimaryActionController.ts';
import { validateGpuControlManagerDependencies } from '@pages/hardware/controllers/gpucontrol/gpuControlManagerValidationController.ts';
import { buildGpuControlActionContext, buildGpuControlDomContext, buildGpuControlManagerViewContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/adapters.ts';
import { buildGpuCapabilitiesLookup } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuCapabilitiesDomain.ts';
import type { GpuCapabilitiesByIndex, GpuCapabilitiesResource } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import { clearGpuControlsPanel, syncGpuControlsPanelVisibility } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/dom.ts';
import { computeApplyCapability } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/effects.ts';
import { hasAnyActionableGpuControls } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/guards.ts';
import type { GpuControlManagerViewContext } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/internalContracts.ts';
import { markGpuSettingsEdited } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlLifecycleManager.ts';
import { parseSavedSettingsState } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/mappers.ts';
import { buildGpuCapabilitiesRenderSignature, buildGpuSlotsRenderSignature } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/gpuControlSignatureManager.ts';
import { cancelAllGpuSaveModes, findFirstPendingGpuIndex, hasActiveGpuSaveMode, hasUnsavedGpuChanges, setGpuSaveMode } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/state.ts';
import { syncGpuControlSoAIBenchUi } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/soaibenchPatchController.ts';
import { renderGpuControls } from '@pages/hardware/controllers/gpucontrol/gpucontrolmanager/view.ts';
import { createDefaultGpuUiState, GpuControlUiStateStore } from '@pages/hardware/controllers/gpucontrol/gpuControlState.ts';
import { normalizeGpuControlTelemetryMap, updateGpuControlTelemetryLabels, type GpuControlTelemetry } from '@pages/hardware/controllers/gpucontrol/gpuControlTelemetryController.ts';
import { getSlotEntryByIndex, syncAllGpuUiStates } from '@pages/hardware/controllers/gpucontrol/gpuControlSync.ts';
import type { ConstructorOptions, GpuControlManagerDependencies, GpuSavedSettingsState, GpuSlotEntry, GpuSnapshot, GpuUiState, SecurityService } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';
import { GpuSoAIBenchController } from '@pages/hardware/controllers/gpucontrol/soaibench/GpuSoAIBenchController.ts';
import { renderGpuResourceStatus } from '@pages/hardware/rendering/gpuResourceStatusWidget.ts';
import type { HardwareGpuResourceState } from '@pages/hardware/controllers/realtime/gpuResourceState.ts';
import { HARDWARE_GPU_CAPABILITIES, HARDWARE_GPU_SLOTS } from '@core/realtime/streammanager/resources/ids.ts';

const str = String;

class GpuControlManager {
    readonly #save: SaveController;
    readonly #dependencies: GpuControlManagerDependencies;
    readonly #security: SecurityService;
    gpuCapabilities: GpuCapabilitiesByIndex | null = null;
    savedGpuSettings: GpuSavedSettingsState | null = null;
    gpuTelemetryByDeviceId: Map<string, GpuControlTelemetry> = new Map();
    readonly #soaibench: GpuSoAIBenchController;
    #uiStateStore = new GpuControlUiStateStore();
    #domRequired = true;
    #resourceState: HardwareGpuResourceState | null = null;
    #gpuCapabilitiesRenderSignature = '';
    #gpuSlotsRenderSignature = '';
    constructor(dependencies: GpuControlManagerDependencies, { security }: ConstructorOptions = {}) {
        this.#dependencies = dependencies;
        this.#security = validateGpuControlManagerDependencies(dependencies, security);
        this.#soaibench = new GpuSoAIBenchController({
            buildActionContext: () => this.#buildActionContext(),
            ensureUiState: (index: string | number) => this.#uiStateStore.ensure(String(index)),
            handleRunsUpdate: (value: JsonValue) => this.#dependencies.handleSoAIBenchRunsUpdate(value),
            syncSoAIBenchUi: (options?: { only?: string[] | null }) => this.#syncSoAIBenchUi(options)
        });
        this.#save = createSaveController({
            headerContextId: 'gpu-controls',
            headerPriority: SAVE_HEADER_PRIORITY_PAGE,
            requestContextLabel: 'GPU controls save',
            units: [
                {
                    id: 'gpu-controls',
                    hasChanges: () => hasUnsavedGpuChanges(this.#uiStateStore.states),
                    save: async () => this.#applyAllPendingGpuChanges()
                }
            ]
        });
        this.#save.attach({ resolveSaveButtons: () => [] });
    }
    get gpuUiState(): Map<string, GpuUiState> {
        return this.#uiStateStore.states;
    }
    hasUnsavedGpuChanges(): boolean {
        return hasUnsavedGpuChanges(this.#uiStateStore.states);
    }
    updateHeaderSaveAction(): void {
        this.#save.notifyChanged();
    }
    async applyAllPendingGpuChanges(): Promise<void> {
        await this.#applyAllPendingGpuChanges();
    }

    async #applyAllPendingGpuChanges(): Promise<void> {
        const maxIterations = 64;
        for (let iteration = 0; iteration < maxIterations; iteration += 1) {
            const index = findFirstPendingGpuIndex(this.#uiStateStore.states);
            if (!index) {
                return;
            }
            await this.handleGpuApplyClick(index);
        }
        throw new Error('GPU apply loop exceeded maximum iterations');
    }
    dispose(): void {
        this.#resourceState?.invalidate();
        this.#soaibench.dispose();
        this.#save.dispose();
    }
    ensureGpuUiState(index: string | number): GpuUiState {
        return this.#uiStateStore.ensure(String(index));
    }
    setGpuTelemetryByDeviceId(source: Record<string, GpuControlTelemetry>): void {
        this.gpuTelemetryByDeviceId = normalizeGpuControlTelemetryMap(source);
        updateGpuControlTelemetryLabels(this.#dependencies.dom.getDocument(), this.gpuTelemetryByDeviceId);
    }
    setCapabilities(capabilities: GpuCapabilitiesResource): void {
        const nextCapabilities = capabilities.success ? buildGpuCapabilitiesLookup(capabilities) : null;
        const nextSignature = buildGpuCapabilitiesRenderSignature(nextCapabilities);
        const shouldRender = nextSignature !== this.#gpuCapabilitiesRenderSignature;
        this.gpuCapabilities = nextCapabilities;
        this.updateGpuStateFromSources({ render: shouldRender });
        this.#gpuCapabilitiesRenderSignature = nextSignature;
    }
    setResourceFreshness(state: HardwareGpuResourceState): void {
        this.#resourceState = state;
        renderGpuResourceStatus(this.#dependencies.dom.getDocument(), state, this.#domRequired, this.#dependencies.getIconSync);
    }
    async retryResources(): Promise<void> {
        const streams = await this.#dependencies.resolveStreamManager();
        await Promise.all([streams.refresh(HARDWARE_GPU_CAPABILITIES), streams.refresh(HARDWARE_GPU_SLOTS)]);
    }
    setSavedSettings(savedSettings: GpuSlotsBuilderResult | null): void {
        const nextSavedSettings = parseSavedSettingsState(savedSettings);
        const nextSignature = buildGpuSlotsRenderSignature(nextSavedSettings);
        const shouldRender = nextSignature !== this.#gpuSlotsRenderSignature;
        this.savedGpuSettings = nextSavedSettings;
        this.updateGpuStateFromSources({ render: shouldRender });
        this.#gpuSlotsRenderSignature = nextSignature;
    }
    setDomRequired(required: boolean): void {
        this.#domRequired = required;
        if (!required) this.#resourceState?.invalidate();
        if (this.#resourceState) renderGpuResourceStatus(this.#dependencies.dom.getDocument(), this.#resourceState, required, this.#dependencies.getIconSync);
        if (!required && this.hasActiveGpuSaveMode()) {
            this.cancelAllGpuSaveModes();
            this.updateHeaderSaveAction();
        }
        syncGpuControlsPanelVisibility(this.#dependencies.dom.getDocument(), required && hasAnyActionableGpuControls(this.gpuCapabilities));
        if (required && this.gpuCapabilities !== null) {
            this.renderGpuControls();
        } else if (!required) {
            clearGpuControlsPanel(this.#dependencies.dom.getDocument());
        }
    }
    getSlotEntryByIndex(index: string | number): GpuSlotEntry | null {
        return getSlotEntryByIndex(this.savedGpuSettings, index);
    }
    updateGpuStateFromSources({ render = true }: { render?: boolean } = {}): void {
        syncAllGpuUiStates({ capabilities: this.gpuCapabilities, savedSettings: this.savedGpuSettings, uiStateStore: this.#uiStateStore, chartOhlc: this.#dependencies.chartOhlc });
        if (!this.#domRequired) {
            return;
        }
        if (render) {
            this.renderGpuControls();
            return;
        }
        this.refreshAllGpuApplyStates();
    }
    renderGpuControls({ only = null }: { only?: string[] | null } = {}): void {
        if (!this.#domRequired) {
            return;
        }
        const controlsVisible = hasAnyActionableGpuControls(this.gpuCapabilities);
        syncGpuControlsPanelVisibility(this.#dependencies.dom.getDocument(), controlsVisible);
        if (!controlsVisible) {
            clearGpuControlsPanel(this.#dependencies.dom.getDocument());
            return;
        }
        renderGpuControls(this.#buildViewContext(), { only });
    }
    #syncSoAIBenchUi(options?: { only?: string[] | null }): void {
        if (!this.#domRequired) {
            return;
        }
        syncGpuControlSoAIBenchUi(this.#buildViewContext(), options);
    }
    setSoAIBenchRuns(value: JsonValue): void {
        this.#soaibench.setRuns(value);
    }
    #buildViewContext(): GpuControlManagerViewContext {
        return buildGpuControlManagerViewContext({ dependencies: this.#dependencies, security: this.#security, capabilitiesByIndex: this.gpuCapabilities, telemetryByDeviceId: this.gpuTelemetryByDeviceId, soaibenchRuns: this.#soaibench.runs, ensureUiState: (index: string | number) => this.ensureGpuUiState(index), refreshApplyState: (index: string | number) => this.refreshApplyState(index), setSliderToAuto: (index: string | number, type: string, explicitDefault?: string | number | null, options?: { preserveManual?: boolean }) => this.setSliderToAuto(index, type, explicitDefault, options), setSliderToManual: (index: string | number, type: string, manualValue?: string | number | null) => this.setSliderToManual(index, type, manualValue), getSliderElements: (index: string | number, type: string) => this.getSliderElements(index, type) });
    }
    getSliderElements(index: string | number, type: string): ReturnType<typeof getSliderElements> {
        return getSliderElements(this.#dependencies.dom.getDocument(), index, type);
    }
    getSliderSnapshot(index: string | number): GpuSnapshot {
        return getSliderSnapshot(this.#dependencies.dom.getDocument(), this.gpuCapabilities, index);
    }
    #getDomContext(): { document: Document; capabilitiesByIndex: GpuCapabilitiesByIndex | null; ensureUiState: (index: string | number) => GpuUiState; refreshApplyState: (index: string | number) => void } {
        return buildGpuControlDomContext({ dependencies: this.#dependencies, capabilitiesByIndex: this.gpuCapabilities, ensureUiState: (index: string | number) => this.ensureGpuUiState(index), refreshApplyState: (index: string | number) => this.refreshApplyState(index) });
    }
    setSliderToAuto(index: string | number, type: string, explicitDefault: string | number | null = null, { preserveManual = false }: { preserveManual?: boolean } = {}): void {
        setSliderToAuto(this.#getDomContext(), index, type, explicitDefault, { preserveManual });
    }
    setSliderToManual(index: string | number, type: string, manualValue: string | number | null = null): void {
        setSliderToManual(this.#getDomContext(), index, type, manualValue);
    }
    updateSliderAutoState(index: string | number, type: string, isAuto: boolean): void {
        updateSliderAutoState(this.#getDomContext(), index, type, isAuto);
    }
    resetGpuUiControls(index: string | number): void {
        resetGpuUiControls(this.#getDomContext(), index);
    }
    markGpuSettingsEdited(index: string | number): void {
        markGpuSettingsEdited(this.ensureGpuUiState(index));
    }
    markGpuStateHydrated(index: string | number): void {
        markGpuStateHydrated((index: string | number) => this.ensureGpuUiState(index), index);
    }
    refreshAllGpuApplyStates(): void {
        this.#uiStateStore.states.forEach((_state: GpuUiState, key: string) => this.refreshApplyState(key));
    }
    refreshApplyState(index: string | number): void {
        refreshGpuApplyState(
            {
                document: this.#dependencies.dom.getDocument(),
                gpuCapabilities: this.gpuCapabilities,
                ensureGpuUiState: (index: string | number) => this.ensureGpuUiState(index),
                getSliderSnapshot: (index: string | number) => this.getSliderSnapshot(index),
                renderGpuControls: (options: { only?: string[] | null }) => this.renderGpuControls(options),
                syncSoAIBenchUi: (options: { only?: string[] | null }) => this.#syncSoAIBenchUi(options),
                updateHeaderSaveAction: () => this.updateHeaderSaveAction()
            },
            index
        );
    }
    async handleGpuApplyClick(index: string | number): Promise<void> {
        const context = this.#buildActionContext();
        await handleGpuApplyClick(context, index, {
            getSnapshot: () => this.getSliderSnapshot(index),
            computeApplyCapability: (snapshot: GpuSnapshot) => {
                const key = str(index);
                const state = this.ensureGpuUiState(key);
                return computeApplyCapability(this.gpuCapabilities, key, state, snapshot);
            }
        });
    }
    async handleGpuSoAIBenchStandardClick(index: string | number): Promise<void> {
        await this.#soaibench.startStandard(index);
    }
    async handleGpuSoAIBenchReopenClick(index: string | number): Promise<void> {
        await this.#soaibench.showRun(index);
    }
    async handleGpuSoAIBenchStressClick(index: string | number): Promise<void> {
        await this.#soaibench.startStress(index);
    }
    async handleGpuSoAIBenchStopClick(index: string | number): Promise<void> {
        await this.#soaibench.stop(index);
    }
    async handleGpuSoAIBenchHistoryClick(index: string | number): Promise<void> {
        await this.#soaibench.showHistory(index);
    }
    handleGpuSoAIBenchToggleClick(index: string | number): void {
        this.#soaibench.toggleActions(index);
    }
    async resetGpuSettings(index: string | number): Promise<void> {
        const context = this.#buildActionContext();
        await resetGpuSettings({ ...context, resetUiControls: (index: string | number) => this.resetGpuUiControls(index) }, index);
    }
    async handleGpuSlotClick(index: string | number, slot: string | number): Promise<void> {
        const context = this.#buildActionContext();
        await handleGpuSlotClick(context, index, slot, { snapshot: () => this.getSliderSnapshot(index) });
    }
    handleGpuBootToggle(index: string | number, enabled: boolean): void {
        handleGpuBootToggle({ ensureUiState: (index: string | number) => this.ensureGpuUiState(index), renderGpuControls: (options?: { only?: string[] | null }) => this.renderGpuControls(options), refreshApplyState: (index: string | number) => this.refreshApplyState(index) }, index, enabled);
    }
    handleGpuSaveButtonClick(event: { stopPropagation?: () => void } | null, index: string | number): void {
        event?.stopPropagation?.();
        if (isNullOrUndefined(index)) return;
        const key = str(index);
        const state = this.ensureGpuUiState(key);
        if (!state.pending && resolveGpuPrimaryAction(state) === 'save') {
            state.showSoAIBenchActions = false;
            this.setGpuSaveMode(key, !state.saveMode);
        }
    }
    handleGpuContainerClick(event: { target?: EventTarget | null }): void {
        if (isElementNode(event?.target) && !event.target.closest('.gpu-slot-button, .gpu-save-btn') && this.hasActiveGpuSaveMode()) {
            this.cancelAllGpuSaveModes();
        }
    }
    hasActiveGpuSaveMode(): boolean {
        return hasActiveGpuSaveMode(this.#uiStateStore.states);
    }
    cancelGpuSaveMode(index: string | number): void {
        this.setGpuSaveMode(index, false);
    }
    cancelAllGpuSaveModes(): void {
        cancelAllGpuSaveModes(this.#uiStateStore.states, (indices: string[]) => this.renderGpuControls({ only: indices }));
    }
    setGpuSaveMode(index: string | number, enabled: boolean): void {
        setGpuSaveMode(
            (index: string | number) => this.ensureGpuUiState(index),
            index,
            enabled,
            (index: string) => this.renderGpuControls({ only: [index] })
        );
    }
    #buildActionContext(): ControlContext {
        return buildGpuControlActionContext({ dependencies: this.#dependencies, capabilitiesByIndex: this.gpuCapabilities, ensureUiState: (index: string | number) => this.ensureGpuUiState(index), renderGpuControls: (options?: { only?: string[] | null }) => this.renderGpuControls(options), syncSoAIBenchUi: (options?: { only?: string[] | null }) => this.#syncSoAIBenchUi(options), getSlotEntryByIndex: (index: string | number) => this.getSlotEntryByIndex(index), setSliderToAuto: (index: string | number, controlType: string) => this.setSliderToAuto(index, controlType), setSliderToManual: (index: string | number, controlType: string, manualValue: string | number | null) => this.setSliderToManual(index, controlType, manualValue), refreshApplyState: (index: string | number) => this.refreshApplyState(index) });
    }
}
export { GPU_CONTROL_TYPES, GPU_PREVIEW_KEY_MAP, GPU_SETTING_KEYS, GPU_SLIDER_CONFIG, GpuControlManager, createDefaultGpuUiState };
export type { GpuControlManagerDependencies, SecurityService };
