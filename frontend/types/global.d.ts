/* SoAI - Global browser runtime declarations [frontend/types/global.d.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

declare var soaiBasePath: string | undefined;
declare var soaiWindowOpenInstrumented: boolean | undefined;
declare var soaiWindowOpenRecords: Array<{ url: string | undefined; name: string | undefined }> | undefined;

type ModuleLoaderStatus = 'pending' | 'loading' | 'ready' | 'error';

interface ModuleLoaderState {
    status: ModuleLoaderStatus;
    timestamp: number;
    dependencies: string[];
    hasError: boolean;
}

interface ModuleLoader {
    registerModule(name: string, dependencies?: readonly string[]): void;
    markModuleReady<T>(name: string, moduleValue: T): void;
    markModuleError(name: string, error: Error): void;
    isModuleReady(name: string): boolean;
    waitForModule<T extends SoAIModuleValue>(name: string, timeoutMs?: number): Promise<T>;
    waitForModules<T extends SoAIModuleValue>(names: readonly string[] | string, timeoutMs?: number): Promise<T[]>;
    getModuleStatus(name: string): ModuleLoaderStatus;
    getAllModuleStates(): Record<string, ModuleLoaderState>;
    MODULE_STATUS: {
        PENDING: ModuleLoaderStatus;
        LOADING: ModuleLoaderStatus;
        READY: ModuleLoaderStatus;
        ERROR: ModuleLoaderStatus;
    };
}

interface SoAIRuntimeRegistry {
    router?: SoAIServiceRegistry['core.router'] | undefined;
}

interface SoAIHardwareSlotsHarness {
    getApplyDisabled: () => boolean;
    setSaveMode: (enabled: boolean) => void;
    clickSlot: (slot: string) => void;
    toggleBoot: (enabled: boolean) => void;
    adjustPower: (value: number) => void;
    state: () => {
        previewSlot: string | null;
        saveMode: boolean;
        bootToggleDirty: boolean;
        applyAtBootDesired: boolean;
        activeSlot: string | null;
        liveSettings: string | null;
    };
    page: {
        gpuController: {
            setGpuSaveMode: (nodeId: string, enabled: boolean) => void;
            handleGpuSlotClick: (nodeId: string, slot: string) => void;
            handleGpuBootToggle: (nodeId: string, enabled: boolean) => void;
            normalizeSlotSettings: (settings: import('../assets/ts/core/types/jsonValues.ts').JsonValue) => string;
            ensureGpuUiState: (nodeId: string) => {
                applyDisabled: boolean;
                saveMode: boolean;
                previewSlot: string | null;
                bootToggleDirty: boolean;
                applyAtBootDesired: boolean;
                activeSlot: string | null;
                liveSettings: string | null;
            };
            refreshApplyState: (nodeId: string) => void;
        };
    };
}

interface SoAIChatTestExports {
    ChatMessageManager: new () => {
        renderImageContent: (payload: { url: string; alt: string }) => string;
    };
    ChatUIManager: new () => {
        elementCache: Map<string, HTMLElement>;
        updateAttachmentsPreview: () => void;
    };
}

interface SoAIVirtualizationHarness {
    populate: (models?: number, logsCount?: number) => void;
    awaitSettled: () => Promise<void>;
    revealModel: (modelId: string) => Promise<boolean>;
    revealLog: (logId: string) => Promise<boolean>;
    revealPlugin: (pluginId: string) => Promise<boolean>;
    revealPrompt: (promptId: string) => Promise<boolean>;
    updatePlugin: (pluginId: string, stablePluginId: string) => Promise<{ updatedReplaced: boolean; stablePreserved: boolean; updatedEntering: boolean } | null>;
    auditEquivalentSnapshots: () => Promise<{
        modelMutations: number;
        pluginMutations: number;
        modelIdentityPreserved: boolean;
        pluginIdentityPreserved: boolean;
        focusPreserved: boolean;
        scrollPreserved: boolean;
        modelCommitDelta: number;
        pluginCommitDelta: number;
        modelFreshness: number | null;
        pluginFreshness: number | null;
        modelNodeCount: number;
        pluginNodeCount: number;
    }>;
    setModelMode: (mode: 'cards' | 'list') => Promise<void>;
    traverseModels: (direction: 'backward' | 'forward') => Promise<string[]>;
    snapshot: () => {
        modelCount: number;
        logCount: number;
        modelMode: 'cards' | 'list';
        modelNodeCount: number;
        logNodeCount: number;
        pluginCount: number;
        promptCount: number;
        pluginNodeCount: number;
        promptNodeCount: number;
        loaderCount: number;
        placeholderOrSpacerCount: number;
        firstModelId: string | null;
        lastModelId: string | null;
        firstLogId: string | null;
        lastLogId: string | null;
        modelScrollTop: number | null;
        modelScrollHeight: number | null;
        modelClientHeight: number | null;
        modelOverflowY: string | null;
        modelContainerRect: DOMRect;
        modelWrapperRect: DOMRect | null;
        modelCommitCount: number;
        logCommitCount: number;
        pluginCommitCount: number;
        promptCommitCount: number;
        maximumFrameGapMs: number;
        maximumLongTaskMs: number;
    };
}

interface SoAITestHarnessRegistry {
    hardwareSlots?: SoAIHardwareSlotsHarness | undefined;
    virtualization?: SoAIVirtualizationHarness | undefined;
    chat?: SoAIChatTestExports | undefined;
}

interface SoAITestRegistry {
    harness?: SoAITestHarnessRegistry | undefined;
    records?: {
        startCalls: string[];
        bootStates: Array<string | null>;
        errors: Error[];
    };
}

interface SoAIBridgeRegistry {
    runtime?: SoAIRuntimeRegistry | undefined;
    tests?: SoAITestRegistry | undefined;
}

interface SoAIReadySnapshot {
    runtime: SoAIRuntimeRegistry;
    tests: SoAITestRegistry;
}

type SoAIModuleValue = SoAIRuntimeRegistry | SoAITestRegistry | SoAIBridgeRegistry | SoAIReadySnapshot | SoAIHardwareSlotsHarness | SoAIChatTestExports | SoAIVirtualizationHarness;

interface SoAINamespace {
    bridge?: SoAIBridgeRegistry | undefined;
    ready?: () => Promise<SoAIReadySnapshot>;
    runtime: SoAIRuntimeRegistry;
    tests: SoAITestRegistry;
}

declare var soaiCspNonce: string | undefined;
declare var getSoaiCspNonce: (() => string | null) | undefined;
declare var soaiCspNonceSupport: { disconnect: () => void } | undefined;

interface Window {
    soaiWindowOpenInstrumented?: boolean;
    soaiWindowOpenRecords?: Array<{ url: string | undefined; name: string | undefined }>;
    soaiRuntimeProbe?: Array<{ type: string; time: number }>;
    hardwareSlotsHarness?: SoAIHardwareSlotsHarness | undefined;
    chatTestExports?: SoAIChatTestExports | undefined;
    virtualizationHarness?: SoAIVirtualizationHarness | undefined;
    soai?: SoAINamespace;
}

interface HTMLInputElement {
    showPicker?: () => void;
}

interface DOMStringMap {
    action?: string;
}
