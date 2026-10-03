/* SoAI - Automation editor submission and explicit save outcomes [frontend/assets/ts/pages/automation/controllers/AutomationEditorSubmissionDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError, extractErrorCode } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';
import type { AutomationDataService, AutomationDefinitionResponse } from '@features/automation/public.ts';
import type { AutomationEditorSubmission } from '@pages/automation/controllers/AutomationConfigurationModalController.ts';
import { resolveAutomationOperationErrorMessage } from '@pages/automation/controllers/AutomationPageErrorNotifier.ts';

const AUTOMATION_REVISION_CONFLICT_CODE = 'automation_revision_conflict';

type AutomationEditorSaveOutcome = { type: 'saved'; automation: AutomationDefinitionResponse; operation: 'create' | 'update' } | { type: 'conflict'; latest: AutomationDefinitionResponse } | { type: 'missing' } | { type: 'failed'; error: Error };

const isNotFoundError = (error: Error): boolean => error instanceof APIError && error.status === 404;

const resolveConflictOutcome = async (dataService: AutomationDataService, automationId: string): Promise<AutomationEditorSaveOutcome> => {
    try {
        return { type: 'conflict', latest: await dataService.getAutomation(automationId) };
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('automationEditorSubmission', 'Failed to load the latest automation after a revision conflict', runtimeError, { context: { automationId } });
        return isNotFoundError(runtimeError) ? { type: 'missing' } : { type: 'failed', error: runtimeError };
    }
};

const submitAutomationEditorSubmission = async (dataService: AutomationDataService, submission: AutomationEditorSubmission): Promise<AutomationEditorSaveOutcome> => {
    try {
        if (submission.type === 'create') {
            return { type: 'saved', automation: await dataService.createAutomation(submission.payload), operation: 'create' };
        }
        return { type: 'saved', automation: await dataService.updateAutomation(submission.automationId, submission.payload, submission.expectedRevision), operation: 'update' };
    } catch (error) {
        const runtimeError = ensureError(error);
        if (submission.type === 'update' && extractErrorCode(runtimeError) === AUTOMATION_REVISION_CONFLICT_CODE) {
            return await resolveConflictOutcome(dataService, submission.automationId);
        }
        if (submission.type === 'update' && isNotFoundError(runtimeError)) {
            errorHandler.warn('automationEditorSubmission', 'Automation was deleted before the update was saved', runtimeError, { context: { automationId: submission.automationId } });
            return { type: 'missing' };
        }
        return { type: 'failed', error: runtimeError };
    }
};

const notifyAutomationEditorSaveFailure = (error: Error, showNotification: (message: string, type?: NotificationType) => void): void => {
    showOperationFailureNotification({ error, operation: i18n.t('common.save'), errorMessage: resolveAutomationOperationErrorMessage(error), showNotification });
};

export { notifyAutomationEditorSaveFailure, submitAutomationEditorSubmission };
export type { AutomationEditorSaveOutcome };
