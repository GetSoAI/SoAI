/* SoAI - Updates page control layer operations controller [frontend/assets/ts/pages/updates/controllers/updatesPageOperationsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import type { UpdatesOperationOutcome, UpdatesProductController } from '@core/edition/updatesContribution.ts';
import type { UpdatesSystemController } from '@pages/updates/controllers/UpdatesSystemController.ts';

interface UpdatesCheckWorkflowDependencies {
    checkButton: HTMLButtonElement;
    systemController: Pick<UpdatesSystemController, 'checkForUpdates'>;
    productController: UpdatesProductController | null;
    beginOperation: () => number;
    finishOperation: (operationRevision: number) => void;
    setButtonLoading: (button: HTMLElement, loading: boolean) => void;
    applyCheckingNotice: () => void;
    applyCheckResults: (operationRevision: number, applicationResult: UpdatesOperationOutcome, osResult: UpdatesOperationOutcome) => void;
}

interface ApplicationInstallWorkflowDependencies {
    button: HTMLButtonElement;
    systemController: Pick<UpdatesSystemController, 'installSystemUpdate'>;
    completeInstall: (outcome: Awaited<ReturnType<UpdatesSystemController['installSystemUpdate']>>) => void;
}

const skippedUpdatesOutcome = (): UpdatesOperationOutcome => ({ type: 'skipped', message: '', updatesCount: 0 });
const failedUpdatesOutcome = (error: Error, context: string): UpdatesOperationOutcome => {
    errorHandler.warn('Updates', context, error);
    return { type: 'error', message: i18n.t('updates.notifications.checkFailed'), updatesCount: 0 };
};

const executeUpdatesCheckWorkflow = async (dependencies: UpdatesCheckWorkflowDependencies): Promise<void> => {
    const operationRevision = dependencies.beginOperation();
    dependencies.setButtonLoading(dependencies.checkButton, true);
    dependencies.applyCheckingNotice();
    try {
        const applicationCheck = dependencies.systemController.checkForUpdates({ manageButtonLoading: false, notifyOnFailure: false }).catch((error) => failedUpdatesOutcome(ensureError(error), 'Application update check failed'));
        const productCheck = resolveProductUpdatesCheck(dependencies);
        const [applicationResult, productResult] = await Promise.all([applicationCheck, productCheck]);
        dependencies.applyCheckResults(operationRevision, applicationResult, productResult);
    } finally {
        dependencies.finishOperation(operationRevision);
        dependencies.setButtonLoading(dependencies.checkButton, false);
    }
};

const resolveProductUpdatesCheck = async (dependencies: UpdatesCheckWorkflowDependencies): Promise<UpdatesOperationOutcome> => {
    if (dependencies.productController === null) {
        return skippedUpdatesOutcome();
    }
    return dependencies.productController.checkUpdates().catch((error) => failedUpdatesOutcome(ensureError(error), 'Product update check failed'));
};

const executeApplicationInstallWorkflow = async (dependencies: ApplicationInstallWorkflowDependencies): Promise<void> => {
    const outcome = await dependencies.systemController.installSystemUpdate(dependencies.button);
    dependencies.completeInstall(outcome);
};

export { executeApplicationInstallWorkflow, executeUpdatesCheckWorkflow };
