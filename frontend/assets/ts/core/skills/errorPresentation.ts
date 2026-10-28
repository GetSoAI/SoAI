/* SoAI - Localized skill operation failures [frontend/assets/ts/core/skills/errorPresentation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { readApiErrorDetail } from '@core/api/errorPayloads.ts';
import { isFiniteInteger } from '@core/typeGuards.ts';

const messages = {
    'skill_invalid_package': () => i18n.t('chat.configuration.skills.errors.invalidPackage'),
    'skill_upload_conflict': () => i18n.t('chat.configuration.skills.errors.uploadConflict'),
    'skill_name_conflict': () => i18n.t('chat.configuration.skills.errors.nameConflict'),
    'skill_library_full': () => i18n.t('chat.configuration.skills.errors.libraryFull'),
    'skill_invocation_unavailable': () => i18n.t('chat.configuration.skills.errors.invocationUnavailable'),
    'skill_import_busy': () => i18n.t('chat.configuration.skills.errors.importBusy'),
    'skill_selection_conflict': () => i18n.t('chat.configuration.skills.conflict'),
    'skill_not_found': () => i18n.t('chat.configuration.skills.errors.notFound'),
    'skill_context_full': () => i18n.t('chat.stream.errors.providerContext')
};

type SkillErrorCode = keyof typeof messages;

const isSkillErrorCode = (code: string): code is SkillErrorCode => Object.hasOwn(messages, code);

const resolveSkillErrorMessage = <T>(code: string | null | undefined, failure?: T): string | null => {
    const reason = readApiErrorDetail(failure, 'reason');
    if (code === 'skill_invalid_package') {
        if (reason === 'archive_integrity') return i18n.t('chat.configuration.skills.errors.archiveIntegrity');
        if (reason === 'archive_unsafe') return i18n.t('chat.configuration.skills.errors.archiveUnsafe');
        if (reason === 'archive_unsupported') return i18n.t('chat.configuration.skills.errors.archiveUnsupported');
        if (reason === 'invalid_filename') return i18n.t('chat.configuration.skills.errors.invalidFilename');
        if (reason === 'resource_limit') {
            const field = readApiErrorDetail(failure, 'field');
            const measured = readApiErrorDetail(failure, 'measured');
            const limit = readApiErrorDetail(failure, 'limit');
            if (typeof field === 'string' && /^[A-Za-z0-9_.-]{1,80}$/u.test(field) && isFiniteInteger(measured) && isFiniteInteger(limit) && Number.isSafeInteger(measured) && Number.isSafeInteger(limit) && limit >= 0 && measured > limit) return i18n.t('chat.configuration.skills.errors.resourceLimit', { field, measured: i18n.formatNumber(measured), limit: i18n.formatNumber(limit) });
        }
        if (reason === 'source_conflict') {
            const locations = readApiErrorDetail(failure, 'locations');
            if (Array.isArray(locations) && typeof locations[0] === 'string' && typeof locations[1] === 'string') return i18n.t('chat.configuration.skills.errors.sourceConflict', { first: locations[0], second: locations[1] });
        }
        if (reason === 'manifest_format') {
            const line = readApiErrorDetail(failure, 'line');
            const column = readApiErrorDetail(failure, 'column');
            if (isFiniteInteger(line) && isFiniteInteger(column) && Number.isSafeInteger(line) && Number.isSafeInteger(column) && line > 0 && column > 0) return i18n.t('chat.configuration.skills.errors.manifestPosition', { line: i18n.formatNumber(line), column: i18n.formatNumber(column) });
            return i18n.t('chat.configuration.skills.errors.manifestFormat');
        }
        if (reason === 'invalid_field') {
            const field = readApiErrorDetail(failure, 'field');
            return i18n.t('chat.configuration.skills.errors.invalidField', { field: typeof field === 'string' ? field : 'SKILL.md' });
        }
    }
    if (code === 'skill_invocation_unavailable') {
        if (reason === 'restriction_unsupported') return i18n.t('chat.configuration.skills.errors.restrictionUnsupported');
        if (reason === 'tool_restricted') return i18n.t('chat.configuration.skills.errors.toolRestricted');
        if (reason === 'argument_conflict') return i18n.t('chat.configuration.skills.errors.argumentConflict');
        if (reason === 'alias_ambiguous') return i18n.t('chat.configuration.skills.errors.aliasAmbiguous');
    }
    if (code === 'skill_invalid_package' && readApiErrorDetail(failure, 'reason') === 'wrapper_name_mismatch') return i18n.t('chat.configuration.skills.errors.wrapperNameMismatch');
    return code && isSkillErrorCode(code) ? messages[code]() : null;
};

export { isSkillErrorCode, resolveSkillErrorMessage };
export type { SkillErrorCode };
