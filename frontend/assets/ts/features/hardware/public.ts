/* SoAI - Hardware feature public surface [frontend/assets/ts/features/hardware/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { formatGigabytes, formatHardwareNumber, formatMemoryUsage, formatPowerWatts, formatProcessCpu, formatProcessMemory, formatProcessRuntime, formatSpeedValue, netmaskToCidr } from '@features/hardware/Formatters.ts';
export { resolveHardwareDeviceDisplayName } from '@features/hardware/deviceNames.ts';
export { TEMPERATURE_CRITICAL_CELSIUS, TEMPERATURE_MAX_SCALE_CELSIUS, TEMPERATURE_WARNING_CELSIUS, resolveTemperatureSeverity } from '@features/hardware/thermalSeverity.ts';
export type { TemperatureSeverity } from '@features/hardware/thermalSeverity.ts';
export { normalizeHistoryComponent, normalizeIdentifier } from '@features/hardware/historyIdentity.ts';
export { buildHardwareValueSeriesFromHistoryPayload } from '@features/hardware/HistorySeries.ts';
export { HistoryStateManager } from '@features/hardware/HistoryState.ts';
export type { HistorySnapshot } from '@features/hardware/HistoryState.ts';
export { CHART_DEFAULTS, METRIC_CONFIG } from '@features/hardware/Metrics.ts';
export { formatUnexpectedSoAIBenchIdentifierLabel, resolveSoAIBenchProfileLabel, resolveSoAIBenchStatusLabel } from '@features/hardware/soaibenchLabels.ts';
export { getSoAIBenchRunsForDevice, hasSoAIBenchHistoryForDevice } from '@features/hardware/soaibenchRunsIndex.ts';
export { DEFAULT_IGNORED_NETWORK_PREFIXES } from '@features/hardware/models/constants.ts';
export { buildNetworkInterfaceModels } from '@features/hardware/models/effects.ts';
export { buildVolumeModels, getCpuDevices, getGpuDevices, getGpuOptionId, isHardwareSnapshot } from '@features/hardware/models/mappers.ts';
export { resolveNetworkSpeedEntry } from '@features/hardware/models/networkSpeed.ts';
export type { HardwareSnapshot, NetworkInterfaceModel, NetworkSpeedEntry, NetworkSpeedSnapshot, VolumeModel } from '@features/hardware/models/types.ts';
export { buildNetworkSummaryText, createNetworkInterfaceRow } from '@features/hardware/networkCardView.ts';
export type { NetworkCardLabelSet, NetworkCardViewHost } from '@features/hardware/networkCardView.ts';
export { buildStorageSummaryText, createStorageInterfaceRow } from '@features/hardware/storageCardView.ts';
export type { StorageCardLabelSet, StorageCardViewHost } from '@features/hardware/storageCardView.ts';
export { anonymizeSystemInfoText } from '@features/hardware/privacyAnonymization.ts';
export type { HardwarePageStorage } from '@features/hardware/pageStorage.ts';
export type { HardwareData } from '@features/hardware/widgets/internalContracts.ts';
export { HardwareWidgetManager } from '@features/hardware/widgets/service.ts';
export { HARDWARE_SOAIBENCH_HISTORY_MODAL_ID, HARDWARE_SOAIBENCH_RUN_MODAL_ID, HARDWARE_SYSTEM_INFO_MODAL_ID } from '@features/hardware/modals/constants.ts';
export { SystemInfoModal } from '@features/hardware/modals/systeminfomodal/service.ts';
export type { SystemInfoModalDependencies, SystemInfoModalHost, SystemInfoModalState } from '@features/hardware/modals/systeminfomodal/types.ts';
export { SoAIBenchHistoryModal } from '@features/hardware/modals/soaibenchhistory/service.ts';
export { HARDWARE_SOAIBENCH_HISTORY_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_COPY_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DOWNLOAD_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_DELETE_LOCAL_ACTION, HARDWARE_SOAIBENCH_HISTORY_ROW_PUBLISH_ACTION, HARDWARE_SOAIBENCH_HISTORY_SORT_ACTION } from '@features/hardware/modals/soaibenchhistory/constants.ts';
export type { SoAIBenchHistoryModalDependencies, SoAIBenchHistoryModalHost, SoAIBenchHistoryOpenRequest, SoAIBenchHistoryRun } from '@features/hardware/modals/soaibenchhistory/types.ts';
export { SoAIBenchRunModal } from '@features/hardware/modals/soaibenchrun/service.ts';
export { SoAIBenchPublicationFlow } from '@features/hardware/soaibenchPublicationFlow.ts';
export type { SoAIBenchPublicationRun } from '@features/hardware/soaibenchPublicationFlow.ts';
export type { SoAIBenchRunModalDependencies, SoAIBenchRunModalHost, SoAIBenchRunOpenRequest, SoAIBenchRunRecord } from '@features/hardware/modals/soaibenchrun/types.ts';
