/* SoAI - Automation editor draft, submission payloads, and change detection [frontend/assets/ts/pages/automation/controllers/configurationmodal/AutomationEditorDraftDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { deepEqual } from '@core/primitives/equality.ts';
import { cloneStructured, toJsonCompatibleObject } from '@core/primitives/clone.ts';
import { rebaseJsonObjectChanges } from '@core/types/jsonObjectPatch.ts';
import type { AutomationColor, AutomationDefinitionResponse, CreateAutomationRequest, UpdateAutomationRequest } from '@features/automation/public.ts';
import type { AutomationRecurrence } from '@pages/automation/types.ts';

interface AutomationEditorDraft {
    title: string;
    color: AutomationColor;
    interactiveToolApproval: boolean;
    timezone: string;
    startLocal: string;
    recurrence: string;
    maxRunMinutes: number | null;
    modelSettings: AutomationDefinitionResponse['modelSettings'];
    turns: readonly string[];
    maxTurns: number;
    maxTurnChars: number;
}

interface AutomationEditorValidDraft extends AutomationEditorDraft {
    recurrence: AutomationRecurrence;
    maxRunMinutes: number;
}

type AutomationEditableField = 'title' | 'color' | 'interactiveToolApproval' | 'timezone' | 'startLocal' | 'recurrence' | 'maxRunMinutes' | 'modelSettings' | 'turns';
type AutomationDefinitionChangeField = AutomationEditableField | 'enabled';

const AUTOMATION_EDITABLE_FIELDS: readonly AutomationEditableField[] = ['title', 'color', 'interactiveToolApproval', 'timezone', 'startLocal', 'recurrence', 'maxRunMinutes', 'modelSettings', 'turns'];

const formatDefinitionChangeField = (field: AutomationDefinitionChangeField): string => {
    switch (field) {
        case 'title':
            return i18n.t('automation.modal.fields.title');
        case 'color':
            return i18n.t('automation.modal.fields.color');
        case 'interactiveToolApproval':
            return i18n.t('automation.modal.fields.interactiveToolApproval');
        case 'timezone':
            return i18n.t('automation.modal.fields.timezone');
        case 'startLocal':
            return i18n.t('automation.modal.fields.start');
        case 'recurrence':
            return i18n.t('automation.modal.fields.recurrence');
        case 'maxRunMinutes':
            return i18n.t('automation.modal.fields.maxRunMinutes');
        case 'modelSettings':
            return i18n.t('automation.modal.fields.modelSettings');
        case 'turns':
            return i18n.t('automation.modal.fields.turns');
        case 'enabled':
            return i18n.t('automation.pane.automations.enabled');
    }
};

const listChangedDraftFields = (base: AutomationEditorDraft, current: AutomationEditorDraft): AutomationEditableField[] => AUTOMATION_EDITABLE_FIELDS.filter((field) => !deepEqual(base[field], current[field]) || (field === 'turns' && (base.maxTurns !== current.maxTurns || base.maxTurnChars !== current.maxTurnChars)));

const rebaseAutomationEditorDraft = (base: AutomationEditorDraft, edited: AutomationEditorDraft, latest: AutomationEditorDraft): AutomationEditorDraft => {
    const rebased = Object.assign(cloneStructured(latest), rebaseJsonObjectChanges(toJsonCompatibleObject(base), toJsonCompatibleObject(edited), toJsonCompatibleObject(latest)));
    if (listChangedDraftFields(base, edited).includes('turns')) {
        rebased.turns = [...edited.turns];
        rebased.maxTurns = edited.maxTurns;
        rebased.maxTurnChars = edited.maxTurnChars;
    }
    return rebased;
};

const listChangedDefinitionFields = (before: AutomationDefinitionResponse, after: AutomationDefinitionResponse): AutomationDefinitionChangeField[] => {
    const changed: AutomationDefinitionChangeField[] = AUTOMATION_EDITABLE_FIELDS.filter((field) => {
        if (field === 'turns') {
            return !deepEqual(before.turns, after.turns) || before.maxTurns !== after.maxTurns || before.maxTurnChars !== after.maxTurnChars;
        }
        return !deepEqual(before[field], after[field]);
    });
    if (before.enabled !== after.enabled) {
        changed.push('enabled');
    }
    return changed;
};

const formatAutomationDefinitionChangeFields = (fields: readonly AutomationDefinitionChangeField[]): string => fields.map(formatDefinitionChangeField).join(', ');

const buildAutomationCreatePayload = (draft: AutomationEditorValidDraft): CreateAutomationRequest => ({
    title: draft.title,
    color: draft.color,
    enabled: true,
    timezone: draft.timezone,
    startLocal: draft.startLocal,
    recurrence: draft.recurrence,
    turns: [...draft.turns],
    maxTurns: draft.turns.length,
    maxTurnChars: Math.max(...draft.turns.map((turn) => turn.length)),
    maxRunMinutes: draft.maxRunMinutes,
    interactiveToolApproval: draft.interactiveToolApproval,
    modelSettings: draft.modelSettings
});

const buildAutomationUpdatePayload = (fields: readonly AutomationEditableField[], draft: AutomationEditorValidDraft): UpdateAutomationRequest => {
    const complete = buildAutomationCreatePayload(draft);
    const payload: UpdateAutomationRequest = {};
    for (const field of fields) {
        if (field === 'title') payload.title = complete.title;
        if (field === 'color') payload.color = complete.color;
        if (field === 'interactiveToolApproval') payload.interactiveToolApproval = complete.interactiveToolApproval;
        if (field === 'timezone') payload.timezone = complete.timezone;
        if (field === 'startLocal') payload.startLocal = complete.startLocal;
        if (field === 'recurrence') payload.recurrence = complete.recurrence;
        if (field === 'maxRunMinutes') payload.maxRunMinutes = complete.maxRunMinutes;
        if (field === 'modelSettings') payload.modelSettings = complete.modelSettings;
        if (field === 'turns') {
            payload.turns = complete.turns;
            payload.maxTurns = draft.maxTurns;
            payload.maxTurnChars = draft.maxTurnChars;
        }
    }
    return payload;
};

export { buildAutomationCreatePayload, buildAutomationUpdatePayload, formatAutomationDefinitionChangeFields, listChangedDefinitionFields, listChangedDraftFields, rebaseAutomationEditorDraft };
export type { AutomationDefinitionChangeField, AutomationEditableField, AutomationEditorDraft, AutomationEditorValidDraft };
