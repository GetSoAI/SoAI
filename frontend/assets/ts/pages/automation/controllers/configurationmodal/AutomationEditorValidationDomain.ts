/* SoAI - Automation editor draft validation [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationEditorValidationDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { parseLocalDateTimeParts } from '@core/time/localDateTime.ts';
import { HARD_MAX_TURN_CHARS, HARD_MAX_TURNS, resolveAutomationRecurrence } from '@pages/automation/controllers/configurationmodal/AutomationConfigurationFormModel.ts';
import type { AutomationEditorDraft, AutomationEditorValidDraft } from '@pages/automation/controllers/configurationmodal/AutomationEditorDraftDomain.ts';

type AutomationEditorIssueField = 'title' | 'timezone' | 'start' | 'recurrence' | 'model' | 'maxRunMinutes' | 'turns' | 'mcp';

interface AutomationEditorIssue {
    field: AutomationEditorIssueField;
    message: string;
}

interface AutomationEditorValidationContext {
    modelIssue: string | null;
    timezoneIssue?: string | null;
    scheduleIssue: string | null;
}

interface AutomationEditorValidation {
    issues: readonly AutomationEditorIssue[];
    invalidTurnIndexes: readonly number[];
    validDraft: AutomationEditorValidDraft | null;
}

const AUTOMATION_EDITOR_ISSUE_FIELDS: readonly AutomationEditorIssueField[] = ['title', 'timezone', 'start', 'recurrence', 'model', 'maxRunMinutes', 'turns', 'mcp'];

const resolveStartIssue = (startLocal: string, scheduleIssue: string | null): string | null => {
    if (!startLocal) {
        return i18n.t('automation.modal.validation.startRequired');
    }
    if (parseLocalDateTimeParts(startLocal) === null) {
        return i18n.t('automation.modal.validation.startInvalid');
    }
    return scheduleIssue;
};

const resolveTurnsIssue = (turns: readonly string[]): { message: string | null; invalidIndexes: number[] } => {
    const emptyIndexes = turns.flatMap((turn, index) => (turn ? [] : [index]));
    if (emptyIndexes.length > 0) {
        return { message: i18n.t('automation.modal.validation.turnsRequired'), invalidIndexes: emptyIndexes };
    }
    if (turns.length > HARD_MAX_TURNS) {
        return { message: i18n.t('automation.modal.validation.tooManyTurns', { max: HARD_MAX_TURNS }), invalidIndexes: [] };
    }
    const longIndexes = turns.flatMap((turn, index) => (turn.length > HARD_MAX_TURN_CHARS ? [index] : []));
    if (longIndexes.length > 0) {
        return { message: i18n.t('automation.modal.validation.turnTooLong', { max: HARD_MAX_TURN_CHARS }), invalidIndexes: longIndexes };
    }
    return { message: null, invalidIndexes: [] };
};

const validateAutomationEditorDraft = (draft: AutomationEditorDraft, context: AutomationEditorValidationContext): AutomationEditorValidation => {
    const issues: AutomationEditorIssue[] = [];
    const addIssue = (field: AutomationEditorIssueField, message: string | null): void => {
        if (message !== null) {
            issues.push({ field, message });
        }
    };
    addIssue('title', draft.title ? null : i18n.t('automation.modal.validation.titleRequired'));
    addIssue('timezone', draft.timezone ? (context.timezoneIssue ?? null) : i18n.t('automation.modal.validation.timezoneRequired'));
    addIssue('start', resolveStartIssue(draft.startLocal, context.scheduleIssue));
    const recurrence = resolveAutomationRecurrence(draft.recurrence);
    addIssue('recurrence', recurrence ? null : i18n.t('automation.modal.validation.recurrenceInvalid'));
    addIssue('model', context.modelIssue);
    addIssue('maxRunMinutes', draft.maxRunMinutes === null ? i18n.t('automation.modal.validation.maxRunMinutesInvalid') : null);
    const turns = resolveTurnsIssue(draft.turns);
    addIssue('turns', turns.message);
    const mcp = draft.modelSettings.mcp;
    addIssue('mcp', mcp.toolsEnabled && mcp.executeTools.includes('todo_write') && mcp.serverConfigs['builtin'] !== false ? null : i18n.t('automation.modal.validation.toolsRequired'));
    const validDraft = issues.length === 0 && recurrence !== null && draft.maxRunMinutes !== null ? { ...draft, recurrence, maxRunMinutes: draft.maxRunMinutes } : null;
    return { issues, invalidTurnIndexes: turns.invalidIndexes, validDraft };
};

export { AUTOMATION_EDITOR_ISSUE_FIELDS, validateAutomationEditorDraft };
export type { AutomationEditorIssue, AutomationEditorIssueField, AutomationEditorValidation, AutomationEditorValidationContext };
