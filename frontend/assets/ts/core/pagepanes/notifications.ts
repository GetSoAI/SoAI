/* SoAI - Localized optional workspace persistence outcomes [frontend/assets/ts/core/pagepanes/notifications.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { PagePanePersistenceStatus } from '@core/pagepanes/session.ts';
import { showNotification } from '@core/ui/notifications/notifications.ts';
import type { PagePaneRetirementOutcome } from '@core/pagepanes/retirement.ts';
import { notifyHandledOperationError, resolveHandledOperationCause } from '@core/operationErrorNotifier.ts';
import { claimErrorReporting } from '@core/errors/reportingOwnership.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { getErrorReference } from '@core/errors/reference.ts';
import { PagePaneUnavailableError } from '@core/pagepanes/placement.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';

const resolvePagePanePersistenceMessage = (status: PagePanePersistenceStatus): string | null => {
    switch (status) {
        case 'unavailable':
            return i18n.t('pagePanes.storageUnavailable');
        case 'quota':
            return i18n.t('pagePanes.storageQuotaExceeded');
        case 'blocked':
            return i18n.t('pagePanes.storageBlocked');
        case 'unsaved':
        case 'not-reconstructible':
        case 'placement':
            return i18n.t('pagePanes.layoutNotSaved');
        case 'invalid':
            return i18n.t('pagePanes.invalidLayout');
        case 'incompatible':
            return i18n.t('pagePanes.incompatibleLayout');
        case 'foreign':
            return i18n.t('pagePanes.foreignLayout');
        case 'route-limit':
        case 'record-limit':
            return i18n.t('pagePanes.layoutTooLarge');
        case 'restore-failed':
            return i18n.t('pagePanes.restoreFailed');
        default:
            return null;
    }
};

const reportPagePanePersistenceStatus = (status: PagePanePersistenceStatus): void => {
    if (status === 'unsaved' || status === 'not-reconstructible' || status === 'placement') return;
    const message = resolvePagePanePersistenceMessage(status);
    if (message) showNotification(message, 'warning', 6000);
};

const reportPagePaneRetirementOutcome = (outcome: PagePaneRetirementOutcome): void => {
    if (outcome.type === 'released') return;
    for (const failure of outcome.failures) {
        if (claimErrorReporting(failure.error)) errorHandler.warn('PagePaneAdmission', `Pane ${failure.paneId} retains incomplete resource release`, failure.error);
    }
    try {
        notifyHandledOperationError({ code: 'page_resource_release_unconfirmed', message: 'Retired pane resource release remains unconfirmed' });
    } catch (error) {
        const failure = ensureError(error);
        if (claimErrorReporting(failure)) errorHandler.error('PagePaneAdmission', 'Pane release recovery notification failed', failure);
    }
};

const reportPagePaneSplitHint = (): void => {
    showNotification(i18n.t('pagePanes.splitUnavailable'), 'info', 6000);
};

const resolvePagePaneActionFailureMessage = (error: Error): string => resolveHandledOperationCause(error) ?? `${i18n.t('common.errors.operationFailed')} ${i18n.t('app.errors.reference', { reference: getErrorReference(error) })}`;

const reportPagePaneActionFailure = (error: Error, operation: 'control' | 'restore' = 'control'): void => {
    if (isAbortError(error) || isLifecycleCancellationError(error)) return;
    if (error instanceof PagePaneUnavailableError) {
        const message = error.reason === 'restore-conflict' ? i18n.t('pagePanes.restoreConflict') : error.reason === 'release-unconfirmed' ? i18n.t('pageOutlet.errors.resourceReleaseUnconfirmed') : i18n.t('pagePanes.placementUnavailable');
        showNotification(message, 'warning', 6000);
        return;
    }
    const reference = getErrorReference(error);
    showOperationFailureNotification({
        error,
        notificationMessage: resolvePagePaneActionFailureMessage(error),
        onUnhandledError: (failure) => {
            if (!claimErrorReporting(failure)) return;
            if (operation === 'restore') errorHandler.warn('PagePaneRestoration', `Pane reconstruction remains unavailable (${reference})`, failure);
            else errorHandler.error('PagePaneControls', `Pane action failed (${reference})`, failure);
        },
        showNotification: (message, level) => {
            showNotification(message, level, 6000);
        }
    });
};

export { reportPagePanePersistenceStatus, resolvePagePanePersistenceMessage, reportPagePaneRetirementOutcome, reportPagePaneSplitHint, reportPagePaneActionFailure, resolvePagePaneActionFailureMessage };
