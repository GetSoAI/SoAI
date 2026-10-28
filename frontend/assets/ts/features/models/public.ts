/* SoAI - Models feature public surface [frontend/assets/ts/features/models/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { MODELS_DOWNLOAD_MODAL_ID, MODELS_EDIT_MODEL_MODAL_ID, MODELS_PROVIDERS_MODAL_ID, MODELS_RENAME_MODEL_MODAL_ID, MODELS_VIRTUAL_MODEL_EDIT_MODAL_ID, MODELS_VIRTUAL_MODELS_MODAL_ID } from '@features/models/modals/constants.ts';
export { applyOpenAICapabilityToggleRequest, reconcileOpenAICapabilityControls, parseOpenAICapabilityToggleRequest, setOpenAICapabilityControlsBusy } from '@features/models/capabilities/openaiCapabilityDom.ts';
export { renderOpenAICapabilityOverrides } from '@features/models/capabilities/openaiCapabilityRendering.ts';
export { createOpenAICapabilityOverrideState, discardOpenAICapabilityOverrideChanges, hasOpenAICapabilityOverrideChanges, hasOpenAICapabilityOverrides, isOpenAICapabilityOverrideConflict, resetOpenAICapabilityOverrideState, resolveOpenAICapabilityOverrideMode, saveOpenAICapabilityOverrideState, setOpenAICapabilityOverrideMode } from '@features/models/capabilities/openaiCapabilityState.ts';
export type { OpenAICapabilityOverrideApi, OpenAICapabilityOverrideCategory, OpenAICapabilityOverrideState } from '@features/models/capabilities/openaiCapabilityState.ts';
export { EditModelModalManager } from '@features/models/modals/editmodelmodal/EditModelModalManager.ts';
export type { EditModelModalHost } from '@features/models/modals/editmodelmodal/EditModelModalManager.ts';
export { RenameModelModalManager } from '@features/models/modals/renamemodal/RenameModelModalManager.ts';
export type { RenameModelModalHost } from '@features/models/modals/renamemodal/RenameModelModalManager.ts';
export { createDownloadModalController } from '@features/models/modals/downloadmodal/downloadModalController.ts';
export type { DownloadModalController } from '@features/models/modals/downloadmodal/downloadModalController.ts';
export type { DownloadModalHost } from '@features/models/modals/downloadmodal/downloadModalTypes.ts';
export { MODEL_DOWNLOAD_OPERATION_FILTER, MODEL_DOWNLOAD_OPERATION_TYPE, MODEL_DOWNLOAD_OPERATION_TYPES } from '@features/models/modelDownloadOperation.ts';
export { VariantProbeManager } from '@features/models/variantprobe/service.ts';
export type { SpeedTest, VariantProbeHost, VariantProbeRenderContext } from '@features/models/variantprobe/types.ts';
export { buildVariantCheckEntry, formatVariantDecimal } from '@features/models/variantprobe/view.ts';
export { applyVariantCheckerboard, buildVariantAdvisoryMarkup, buildVariantErrorMarkup, buildVariantLoadingMarkup } from '@features/models/variantprobe/variantrendering/view.ts';
export { applyModelSearchCheckerboard, buildModelSearchEmptyMarkup, buildModelSearchEntry, buildModelSearchErrorMarkup, buildModelSearchLoadingMarkup } from '@features/models/search/modelSearchRendering.ts';
export { resolveModelSearchErrorMessage } from '@features/models/search/modelSearchErrors.ts';
export { parseModelSearchResults } from '@features/models/search/modelSearchResults.ts';
export type { ModelSearchResult, ModelSearchResults } from '@features/models/search/modelSearchTypes.ts';
export { findActiveModelDownloadOperation, getActiveModelDownloadOperations } from '@features/models/downloads/modelDownloadOperations.ts';
export { runModelDownload } from '@features/models/downloads/modelDownloadRun.ts';
export type { ModelDownloadOutcome } from '@features/models/downloads/modelDownloadRun.ts';
export { waitForModelCatalogChange } from '@features/models/providerform/modelCatalogChange.ts';
export { submitProviderForm, validateProviderForm } from '@features/models/providerform/providerSubmission.ts';
export { resolvePluginUnavailableReason } from '@features/models/modals/downloadmodal/pluginAvailability.ts';
export { resolveRepositoryLinkData } from '@features/models/modals/downloadmodal/mappers.ts';
export type { ProviderCreatePayload, ProviderFormField, ProviderFormValues } from '@features/models/providerform/providerSubmission.ts';
export { ProvidersManager } from '@features/models/modals/providersmodal/ProvidersManager.ts';
export type { ProvidersManagerDependencies } from '@features/models/modals/providersmodal/contracts.ts';
export { VirtualModelsManager } from '@features/models/modals/virtualmodelsmodal/VirtualModelsManager.ts';
export type { ModelEntry, VirtualModelRecord, VirtualModelState, VirtualModelsHost, VirtualModelsManagerDependencies } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

export { highlightVariantProbeSelection } from '@features/models/variantprobe/variantProbeSelectionManager.ts';
