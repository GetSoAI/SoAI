/* SoAI - Hardware page GPU control errors [frontend/assets/ts/pages/hardware/controllers/gpucontrol/gpuControlErrors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { extractErrorCode } from '@core/errors/coerce.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

const CONTROL_BACKEND_MISSING_FRAGMENT = 'no supported control backend';

export const resolveGpuApiErrorCode = (error: Error): string | null => {
    return extractErrorCode(error);
};

const textContainsMissingControlBackend = (value: string): boolean => value.toLowerCase().includes(CONTROL_BACKEND_MISSING_FRAGMENT);

const arrayContainsMissingControlBackend = (values: readonly JsonValue[]): boolean => {
    for (const value of values) {
        if (containsMissingControlBackend(value)) {
            return true;
        }
    }
    return false;
};

const objectContainsMissingControlBackend = (value: Record<string, JsonValue>): boolean => {
    for (const candidate of Object.values(value)) {
        if (containsMissingControlBackend(candidate)) {
            return true;
        }
    }
    return false;
};

const containsMissingControlBackend = (value: JsonValue): boolean => {
    if (isString(value)) {
        return textContainsMissingControlBackend(value);
    }
    if (isArray(value)) {
        return arrayContainsMissingControlBackend(value);
    }
    if (isObject(value)) {
        return objectContainsMissingControlBackend(value);
    }
    return false;
};

export const isGpuControlBackendMissingError = (error: Error): boolean => {
    if (textContainsMissingControlBackend(error.message)) {
        return true;
    }
    if (!isObject(error)) {
        return false;
    }
    return containsMissingControlBackend(error.message);
};

export const resolveGpuActionFailureMessage = (code: string | null | undefined): string => {
    switch (code) {
        case 'gpu_control_preparation_failed':
            return i18n.t('hardware.gpu.errors.controlPreparationFailed');
        case 'invalid_gpu_id':
            return i18n.t('hardware.gpu.errors.invalidGpuId');
        case 'invalid_slot':
            return i18n.t('hardware.gpu.errors.invalidSlot');
        case 'invalid_payload':
            return i18n.t('hardware.gpu.errors.invalidPayload');
        case 'no_settings':
            return i18n.t('hardware.gpu.errors.noSettings');
        case 'device_not_found':
            return i18n.t('hardware.gpu.errors.deviceNotFound');
        case 'no_gpus':
            return i18n.t('hardware.gpu.errors.noGpus');
        case 'slot_empty':
            return i18n.t('hardware.gpu.errors.slotEmpty');
        case 'slot_unchanged':
            return i18n.t('hardware.gpu.errors.slotUnchanged');
        case 'boot_unchanged':
            return i18n.t('hardware.gpu.errors.bootUnchanged');
        case 'slot_requires_apply':
            return i18n.t('hardware.gpu.errors.slotRequiresApply');
        case 'apply_failed':
            return i18n.t('hardware.gpu.errors.applyFailed');
        case 'device_unavailable':
            return i18n.t('hardware.gpu.errors.deviceUnavailable');
        case 'hardware_mutation_disabled':
            return i18n.t('hardware.gpu.errors.hardwareMutationDisabled');
        case 'gpu_activity_conflict':
            return i18n.t('hardware.gpu.errors.gpuActivityConflict');
        case 'hardware_unavailable':
            return i18n.t('hardware.gpu.errors.hardwareUnavailable');
        case 'gpu_error':
            return i18n.t('hardware.gpu.errors.gpuError');
        case 'slot_error':
            return i18n.t('hardware.gpu.errors.slotError');
        case 'invalid_request_error':
            return i18n.t('hardware.gpu.errors.invalidPayload');
        case 'recovery_reconciled':
            return i18n.t('hardware.gpu.errors.recoveryReconciled');
        case 'recovery_unresolved':
            return i18n.t('hardware.gpu.errors.recoveryUnresolved');
        default:
            return i18n.t('common.errors.operationFailed');
    }
};
