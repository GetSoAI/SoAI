/* SoAI - Automation page management actions [frontend/assets/ts/pages/automation/controllers/automationManagementActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { AutomationDefinitionResponse } from '@features/automation/public.ts';
import type { AutomationPageState } from '@pages/automation/types.ts';

const requireAutomationId = (element: HTMLElement, actionLabel: string): string => {
    const candidate = element.dataset['automationId'] ?? '';
    const trimmed = candidate.trim();
    if (!trimmed) {
        throw new Error(`${actionLabel} action requires data-automation-id`);
    }
    return trimmed;
};

const resolveAutomationById = (automations: readonly AutomationDefinitionResponse[], automationId: string): AutomationDefinitionResponse => {
    const match = automations.find((entry) => entry.id === automationId) ?? null;
    if (!match) {
        throw new Error('Automation not found');
    }
    return match;
};

const requireCheckboxInput = (element: HTMLElement): HTMLInputElement => {
    if (!(element instanceof HTMLInputElement) || element.type !== 'checkbox') {
        throw new TypeError('Toggle automation enabled action must be a checkbox input');
    }
    return element;
};

const confirmDeleteAutomation = async (automation: { id: string; title: string }): Promise<boolean> => {
    return await requireDialogsService().showConfirmation({
        title: i18n.t('automation.confirmations.deleteTitle'),
        message: i18n.t('automation.confirmations.deleteMessage', { title: automation.title }),
        confirmText: i18n.t('common.delete'),
        cancelText: i18n.t('common.cancel'),
        variant: 'danger'
    });
};

const clearSelectionIfMatchesAutomation = (state: AutomationPageState, automationId: string): AutomationPageState => {
    const selected = state.selectedZoneKey;
    if (!selected) {
        return state;
    }
    const prefix = `${automationId}:`;
    if (!selected.startsWith(prefix)) {
        return state;
    }
    return { ...state, selectedZoneKey: null };
};

export { clearSelectionIfMatchesAutomation, confirmDeleteAutomation, requireAutomationId, requireCheckboxInput, resolveAutomationById };
