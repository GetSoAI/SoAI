/* SoAI - Localized operation failure causes [frontend/assets/ts/core/errors/operationCausePresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { readApiErrorField } from '@core/apiError.ts';
import { isFiniteInteger, isFiniteNumber, isStringArray } from '@core/typeGuards.ts';
import { readApiErrorDetail, readApiErrorMetadataPath } from '@core/api/errorPayloads.ts';
import { FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE } from '@core/api/contracts/fileExplorerListingContracts.ts';
import { formatBytes } from '@core/primitives/byteSize.ts';
import { readSpeechSetupReason } from '@core/speechsetup/failure.ts';
import { speechSetupReasonMessage } from '@core/speechsetup/presentation.ts';
import { resolveObservedSpeechReason } from '@core/speechsetup/service.ts';

const resolveOperationCauseMessage = <T>(code: string | null, failure?: T): string | null => {
    switch (code) {
        case 'runtime_verification_failed':
            return readApiErrorDetail(failure, 'reason') === 'runtime_probe_illegal_instruction' ? i18n.t('plugins.errors.runtimeIllegalInstruction') : i18n.t('plugins.errors.runtimeVerificationFailed');
        case 'invalid_request_error':
        case 'context_window_exceeded': {
            const requested = readApiErrorDetail(failure, 'requested_tokens');
            const available = readApiErrorDetail(failure, 'available_tokens');
            if (readApiErrorDetail(failure, 'type') !== 'context_window_exceeded' || readApiErrorDetail(failure, 'token_scope') !== 'prompt' || !isFiniteInteger(requested) || !isFiniteInteger(available) || !Number.isSafeInteger(requested) || !Number.isSafeInteger(available) || available <= 0 || requested <= available) return null;
            return i18n.t('chat.errors.promptBudgetExceeded', { requested: i18n.formatNumber(requested), available: i18n.formatNumber(available) });
        }
        case 'managed_compiler_unavailable':
            return i18n.t('plugins.errors.managedCompilerUnavailable');
        case 'backend_runtime_incompatible': {
            const reasons = readApiErrorDetail(failure, 'reasons');
            return resolveBackendCompatibilityMessage(isStringArray(reasons) ? reasons : []);
        }
        case 'backend_runtime_selection_changed':
            return i18n.t('plugins.errors.backendRuntimeSelectionChanged');
        case 'backend_runtime_unverified':
            return i18n.t('plugins.errors.backendRuntimeUnverified');
        case 'gpu_inventory_timeout':
            return readApiErrorDetail(failure, 'reason') === 'native_timeout' ? i18n.t('hardware.errors.gpuDiscoveryNativeTimeout') : readApiErrorDetail(failure, 'reason') === 'admission_deadline' ? i18n.t('hardware.errors.gpuDiscoveryBusy') : i18n.t('hardware.errors.gpuDiscoveryTimeout');
        case 'gpu_inventory_query_failed':
            return resolveGpuDiscoveryMessage(readApiErrorDetail(failure, 'reason'));
        case 'file_destination_exists':
            return i18n.t('fileExplorer.errors.destinationExists');
        case 'file_content_changed':
            return i18n.t('fileExplorer.errors.contentChanged');
        case 'file_cleanup_incomplete':
            return i18n.t('fileExplorer.errors.cleanupIncomplete');
        case 'file_publication_uncertain':
            return i18n.t('fileExplorer.errors.publicationUncertain');
        case 'insufficient_disk_space':
            return resolveStorageHeadroomMessage(failure);
        case FILE_EXPLORER_LISTING_EXPIRED_ERROR_CODE:
            return i18n.t('fileExplorer.errors.listingExpired');
        case 'service_unavailable':
            return readApiErrorDetail(failure, 'reason') === 'durable_queue_full' ? i18n.t('chat.errors.durableQueueFull') : null;
        case 'media_dependency_unavailable':
            return i18n.t('speechSetup.errors.mediaDependencyUnavailable');
        case 'ollama_responses_settings_unsupported':
            return i18n.t('plugins.errors.ollamaResponsesSettingsUnsupported');
        case 'gpu_control_preparation_failed':
            return i18n.t('hardware.gpu.errors.controlPreparationFailed');
        case 'gpu_sensor_permission_denied':
            return i18n.t('hardware.errors.gpuSensorPermissionDenied');
        case 'gpu_observation_unavailable':
            return readApiErrorDetail(failure, 'reason') === 'timeout' ? i18n.t('hardware.errors.gpuObservationTimeout') : i18n.t('hardware.errors.gpuObservationUnavailable');
        case 'transcription_model_unavailable':
        case 'transcription_option_unsupported': {
            const scope = readApiErrorDetail(failure, 'speech_scope') === 'voice' ? 'voice' : 'media';
            const reason = resolveObservedSpeechReason(readSpeechSetupReason(readApiErrorDetail(failure, 'reason')), scope);
            return reason === null ? i18n.t('speechSetup.errors.noVoiceModel') : speechSetupReasonMessage(reason, '', scope);
        }
        case 'text_to_speech_model_unavailable':
            return speechSetupReasonMessage(resolveObservedSpeechReason(null, 'synthesis') ?? 'no_model_installed', '', 'synthesis');
        case 'model_not_found':
            return i18n.t('models.errors.modelNotFound');
        case 'remote_model_search_timeout':
            return i18n.t('models.errors.modelSearchTimeout');
        case 'rag_embedding_model_unavailable':
            return i18n.t('chat.errors.ragEmbeddingModelUnavailable');
        case 'rag_documents_not_indexed':
            return i18n.t('chat.errors.ragDocumentsNotIndexed');
        case 'model_repository_unavailable':
            return i18n.t('models.errors.repositoryUnavailable');
        case 'model_parameter_schema_unavailable':
            return readApiErrorDetail(failure, 'reason') === 'plugin_operation_in_progress' ? i18n.t('models.errors.parameterSchemaBusy') : i18n.t('models.errors.parameterSchemaUnavailable');
        case 'model_parameters_apply_failed':
            return i18n.t('models.errors.parametersApplyFailed');
        case 'plugin_configuration_changed':
            return i18n.t('plugins.errors.configurationChanged');
        case 'plugin_configuration_apply_failed':
            return i18n.t('plugins.errors.configurationApplyFailed');
        case 'plugin_configuration_busy':
            return i18n.t('plugins.errors.configurationBusy');
        case 'model_configuration_missing':
            return i18n.t('models.errors.configurationMissing');
        case 'model_architecture_unsupported':
            return i18n.t('models.errors.architectureUnsupported');
        case 'gpu_binding_identity_conflict':
            return i18n.t('hardware.errors.gpuBindingIdentityConflict');
        case 'cuda_device_architecture_unsupported':
            return i18n.t('models.errors.cudaDeviceArchitectureUnsupported');
        case 'native_cpu_features_unsupported':
            return i18n.t('models.errors.nativeCpuFeaturesUnsupported');
        case 'openvino_tensor_shape_incompatible':
            return i18n.t('models.errors.openvinoTensorShapeIncompatible');
        case 'timeout_error':
            return resolveExecutionTimeoutMessage(failure);
        case 'model_tool_calling_unsupported':
            return i18n.t('chat.errors.modelToolCallingUnsupported');
        case 'context_window_override_invalid':
            return i18n.t('chat.errors.contextWindowOverrideInvalid');
        case 'context_window_override_conflict':
            return i18n.t('chat.errors.contextWindowOverrideConflict');
        case 'vulkan_runtime_unavailable':
            return i18n.t('hardware.errors.vulkanRuntimeUnavailable');
        case 'vulkan_query_timeout':
            return i18n.t('hardware.errors.vulkanQueryTimeout');
        case 'vulkan_format_unsupported':
            return i18n.t('hardware.errors.vulkanFormatUnsupported');
        case 'vulkan_device_unavailable':
            return i18n.t('hardware.errors.vulkanDeviceUnavailable');
        case 'vulkan_identity_unavailable':
            return i18n.t('hardware.errors.vulkanIdentityUnavailable');
        case 'vulkan_identity_conflict':
            return i18n.t('hardware.errors.vulkanIdentityConflict');
        case 'vulkan_device_ambiguous':
            return i18n.t('hardware.errors.vulkanDeviceAmbiguous');
        case 'gpu_setting_out_of_range':
            return resolveGpuRangeMessage(readApiErrorMetadataPath(failure, ['payload', 'error', 'details']) ?? readApiErrorMetadataPath(failure, ['data', 'error', 'details']) ?? readApiErrorField(failure, 'detail'));
        case 'gpu_inventory_busy':
            return readApiErrorDetail(failure, 'reason') === 'topology_changed' ? i18n.t('hardware.errors.gpuDiscoveryChanged') : i18n.t('hardware.errors.gpuInventoryBusy');
        case 'gpu_clock_combination_unsupported':
            return i18n.t('hardware.errors.gpuClockCombinationUnsupported');
        case 'gpu_clock_conversion_unavailable':
            return i18n.t('hardware.errors.gpuClockConversionUnavailable');
        case 'soaibench_publication_cancelled':
            return i18n.t('hardware.errors.soaibenchPublicationCancelled');
        case 'soaibench_publication_incomplete':
            return i18n.t('hardware.errors.soaibenchPublicationIncomplete');
        case 'ollama_pull_eof':
            return `${i18n.t('models.errors.ollamaPullEof')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'ollama_pull_timeout':
            return `${i18n.t('models.errors.ollamaPullTimeout')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'ollama_pull_disconnected':
            return `${i18n.t('models.errors.ollamaPullDisconnected')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'ollama_pull_rejected':
            return `${i18n.t('models.errors.ollamaPullRejected')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'ollama_pull_protocol_invalid':
            return `${i18n.t('models.errors.ollamaPullProtocolInvalid')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'ollama_pull_target_missing':
            return `${i18n.t('models.errors.ollamaPullTargetMissing')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'ollama_pull_cache_failed':
            return `${i18n.t('models.errors.ollamaPullCacheFailed')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'ollama_pull_cleanup_failed':
            return i18n.t('models.errors.ollamaPullCleanupFailed');
        case 'ollama_pull_preparation_failed':
            return `${i18n.t('models.errors.ollamaPullPreparationFailed')} ${i18n.t('models.errors.ollamaPullRecovery')}`;
        case 'file_in_use':
            return i18n.t('fileExplorer.errors.fileInUse');
        case 'file_access_denied':
            return i18n.t('common.errors.fileAccessDenied');
        case 'file_operation_failed':
            return i18n.t('common.errors.fileOperationFailed');
        case 'runtime_startup_timeout':
            return i18n.t('common.errors.runtimeStartupTimeout');
        case 'runtime_verification_timeout':
            return i18n.t('common.errors.runtimeVerificationTimeout');
        case 'gpu_recovery_identity_conflict':
            return i18n.t('hardware.errors.gpuRecoveryIdentityConflict');
        case 'gpu_slot_alias_conflict':
            return i18n.t('hardware.errors.gpuSlotAliasConflict');
        case 'model_conversion_failed':
            return i18n.t('plugins.errors.modelConversionFailed');
        case 'model_conversion_dependency_missing':
            return i18n.t('plugins.errors.modelConversionDependencyMissing');
        case 'backend_docker_cli_missing':
            return i18n.t('plugins.errors.backendDockerCliMissing');
        case 'plugin_lifecycle_locked':
            return i18n.t('plugins.errors.backendLifecycleLocked');
        case 'backend_docker_engine_unavailable':
            return i18n.t('plugins.errors.backendDockerEngineUnavailable');
        case 'backend_docker_buildx_unavailable':
            return i18n.t('plugins.errors.backendDockerBuildxUnavailable');
        case 'backend_docker_builder_unavailable':
            return i18n.t('plugins.errors.backendDockerBuilderUnavailable');
        case 'backend_docker_storage_unavailable':
            return i18n.t('plugins.errors.backendDockerStorageUnavailable');
        case 'backend_docker_storage_unmapped':
            return i18n.t('plugins.errors.backendDockerStorageUnmapped');
        case 'backend_docker_storage_access_denied':
            return i18n.t('plugins.errors.backendDockerStorageAccessDenied');
        case 'backend_docker_storage_changed':
            return i18n.t('plugins.errors.backendDockerStorageChanged');
        case 'ipc_cancellation_cleanup_failed':
            return i18n.t('plugins.errors.backendCancellationCleanupFailed');
        case 'melotts_container_cleanup_failed':
            return i18n.t('plugins.errors.melottsContainerCleanupFailed');
        default:
            return null;
    }
};

const resolveGpuDiscoveryMessage = <T>(reason: T): string => {
    switch (reason) {
        case 'native_exit':
            return i18n.t('hardware.errors.gpuDiscoveryQueryFailed');
        case 'empty_response':
            return i18n.t('hardware.errors.gpuDiscoveryEmpty');
        case 'invalid_response':
            return i18n.t('hardware.errors.gpuDiscoveryInvalid');
        case 'runtime_unavailable':
            return i18n.t('hardware.errors.gpuDiscoveryRuntimeUnavailable');
        case 'permission_denied':
            return i18n.t('hardware.errors.gpuDiscoveryPermissionDenied');
        default:
            return i18n.t('hardware.errors.gpuDiscoveryUnavailable');
    }
};

const resolveExecutionTimeoutMessage = <T>(failure: T): string | null => {
    const budget = readApiErrorDetail(failure, 'budget_seconds');
    const elapsed = readApiErrorDetail(failure, 'elapsed_seconds');
    if (!isFiniteNumber(budget) || !isFiniteNumber(elapsed) || budget < 0 || elapsed < 0) {
        return null;
    }
    let owner: string;
    switch (readApiErrorDetail(failure, 'budget_source')) {
        case 'caller_request':
            owner = i18n.t('common.errors.executionTimeoutRequestLimit');
            break;
        case 'plugin_health':
            owner = i18n.t('common.errors.executionTimeoutPluginBudget');
            break;
        default:
            return null;
    }
    const values = { budget: i18n.formatNumber(budget, { minimumFractionDigits: 1, maximumFractionDigits: 1 }), elapsed: i18n.formatNumber(elapsed, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) };
    switch (readApiErrorDetail(failure, 'phase')) {
        case 'response':
            return `${i18n.t('common.errors.executionTimeoutResponse', values)} ${owner}`;
        case 'initial_response':
            return `${i18n.t('common.errors.executionTimeoutInitialResponse', values)} ${owner}`;
        case 'first_token':
            return `${i18n.t('common.errors.executionTimeoutFirstToken', values)} ${owner}`;
        case 'buffered_response':
            return `${i18n.t('common.errors.executionTimeoutBufferedResponse', values)} ${owner}`;
        default:
            return null;
    }
};

const resolveGpuRangeMessage = <T>(details: T): string => {
    const field = readApiErrorField(details, 'field');
    const requested = readApiErrorField(details, 'requested');
    const minimum = readApiErrorField(details, 'minimum');
    const maximum = readApiErrorField(details, 'maximum');
    const unit = readApiErrorField(details, 'unit');
    let label: string | null = null;
    let expectedUnit: string | null = null;
    switch (field) {
        case 'core_clock':
            label = i18n.t('hardware.metrics.labels.coreClock');
            expectedUnit = 'MHz';
            break;
        case 'mem_clock':
            label = i18n.t('hardware.metrics.labels.memoryClock');
            expectedUnit = 'MHz';
            break;
        case 'power_limit':
            label = i18n.t('hardware.gpu.controls.power_limit');
            expectedUnit = 'W';
            break;
        case 'fan_speed':
            label = i18n.t('hardware.gpu.controls.fan_speed');
            expectedUnit = '%';
            break;
    }
    if (label !== null && unit === expectedUnit && typeof unit === 'string' && isFiniteInteger(requested) && isFiniteInteger(minimum) && isFiniteInteger(maximum) && minimum <= maximum && (requested < minimum || requested > maximum)) {
        return i18n.t('hardware.errors.gpuSettingRange', { field: label, requested, minimum, maximum, unit });
    }
    return i18n.t('hardware.errors.gpuSettingOutOfRange');
};

const resolveBackendCompatibilityMessage = (reasons: readonly string[]): string => (reasons.includes('cpu_features_unsupported') ? i18n.t('plugins.errors.backendCpuInstructionsUnavailable') : i18n.t('plugins.errors.backendRuntimeIncompatible'));

const resolveStorageHeadroomMessage = <T>(failure: T): string => {
    const message = i18n.t('common.errors.storageHeadroomInsufficient');
    const required = readApiErrorDetail(failure, 'required_with_tolerance_bytes');
    const available = readApiErrorDetail(failure, 'available_bytes');
    if (!isFiniteInteger(required) || !isFiniteInteger(available) || !Number.isSafeInteger(required) || !Number.isSafeInteger(available) || available < 0 || required <= available) return message;
    return `${message} ${i18n.t('common.errors.storageHeadroomValues', { required: formatBytes(required), available: formatBytes(available) })}`;
};

export { resolveOperationCauseMessage, resolveBackendCompatibilityMessage };
