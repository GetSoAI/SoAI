/* SoAI - Hardware page GPU control sync [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeLiveSettings, normalizeSlotId, normalizeSlotSettings, settingsEqual, slotExists } from '@pages/hardware/controllers/gpucontrol/gpuControlNormalization.ts';
import type { GpuControlUiStateStore } from '@pages/hardware/controllers/gpucontrol/gpuControlState.ts';
import type { GpuCapabilities, GpuCapabilitiesByIndex } from '@core/realtime/streammanager/resources/gpuCapabilitiesContracts.ts';
import type { ChartOhlcNumeric, GpuSavedSettingsState, GpuSlotEntry, GpuUiState } from '@pages/hardware/controllers/gpucontrol/gpuControlTypes.ts';

export const getSlotEntryByIndex = (savedSettings: GpuSavedSettingsState | null, index: string | number): GpuSlotEntry | null => {
    const byIndex = savedSettings?.byIndex ?? null;
    const entry = byIndex?.[String(index)];
    return entry ?? null;
};

export const syncGpuUiState = ({ index, capabilities, savedSettings, uiStateStore, chartOhlc }: { index: string | number; capabilities: GpuCapabilitiesByIndex | null; savedSettings: GpuSavedSettingsState | null; uiStateStore: GpuControlUiStateStore; chartOhlc: ChartOhlcNumeric }): void => {
    const key = String(index);
    const caps: GpuCapabilities | null = capabilities?.[key] ?? null;
    const slotEntry = getSlotEntryByIndex(savedSettings, index);
    const state: GpuUiState = uiStateStore.ensure(key);
    state.slotMetadata = slotEntry;
    state.deviceId = caps?.deviceId ?? slotEntry?.deviceId ?? state.deviceId ?? null;

    const slotLive = slotEntry?.live;
    const capsLive = caps?.live;
    state.activeSlot = normalizeSlotId(slotLive?.activeSlot ?? capsLive?.activeSlot ?? caps?.activeSlot ?? null);

    const slotBoot = slotEntry?.boot;
    const bootEnabled = !!slotBoot?.enabled;
    state.bootSlot = normalizeSlotId(bootEnabled ? (slotBoot?.slot ?? null) : (slotLive?.bootSlot ?? capsLive?.bootSlot ?? caps?.bootSlot ?? null));

    state.liveSettings = normalizeLiveSettings(chartOhlc, caps, slotEntry);

    if (!state.initialized && state.deviceId) {
        state.initialized = true;
    }

    if (state.previewSlot && !slotExists(state.previewSlot, slotEntry)) {
        state.previewSlot = null;
        state.previewSettings = null;
        state.previewSource = 'live';
        state.previewHydrated = false;
        state.applyAtBootDesired = false;
        state.bootToggleDirty = false;
        state.canStoreAppliedSettings = false;
    }

    if (state.previewSlot && slotEntry?.slots) {
        const slotData = slotEntry.slots[state.previewSlot] ?? null;
        const rawSettings = slotData?.settings ?? {};
        const normalized = normalizeSlotSettings(rawSettings, slotData?.fieldModes ?? null);
        if (!settingsEqual(normalized, state.previewSettings)) {
            state.previewSettings = normalized;
            state.previewHydrated = false;
        }
    }

    if (!state.previewSlot) {
        state.previewSettings = null;
        state.previewSource = 'live';
    }

    if (state.previewSlot && slotEntry && !state.bootToggleDirty) {
        const boot = slotEntry.boot;
        state.applyAtBootDesired = !!(boot?.enabled && String(boot.slot) === state.previewSlot);
    }
};

export const syncAllGpuUiStates = ({ capabilities, savedSettings, uiStateStore, chartOhlc }: { capabilities: GpuCapabilitiesByIndex | null; savedSettings: GpuSavedSettingsState | null; uiStateStore: GpuControlUiStateStore; chartOhlc: ChartOhlcNumeric }): void => {
    if (!capabilities) {
        uiStateStore.clear();
        return;
    }
    const active = new Set(Object.keys(capabilities));
    active.forEach((index) => syncGpuUiState({ index, capabilities, savedSettings, uiStateStore, chartOhlc }));
    Array.from(uiStateStore.states.keys()).forEach((key) => {
        if (!active.has(key)) uiStateStore.states.delete(key);
    });
};
