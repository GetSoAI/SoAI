/* SoAI - Wizard product access document and selection lifecycle [frontend/assets/ts/pages/wizard/services/productAccessController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LicensingLegalFlow } from '@core/api/contracts/licensingLegalDocumentContracts.ts';
import { i18n } from '@core/i18n/index.ts';
import { isLicensingOperationInProgress } from '@core/licensing/operationLifecycle.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { WizardPageServiceHost } from '@pages/wizard/services/contracts.ts';
import type { ProductAccessFlow } from '@pages/wizard/types.ts';

interface WizardProductAccessControllerDependencies {
    host: WizardPageServiceHost;
    clearSensitiveInput: () => void;
    clearInlineError: () => void;
}

const readProductAccessFlow = (value: string): ProductAccessFlow | null => {
    if (value === 'evaluation' || value === 'online_activation' || value === 'offline_activation') return value;
    return null;
};

class WizardProductAccessController {
    readonly #dependencies: WizardProductAccessControllerDependencies;
    #selectionRevision = 0;

    constructor(dependencies: WizardProductAccessControllerDependencies) {
        this.#dependencies = dependencies;
    }

    invalidate(): void {
        this.#selectionRevision += 1;
    }

    async loadDocuments(): Promise<void> {
        const status = this.#dependencies.host.view.state.status;
        let flows: readonly LicensingLegalFlow[] = [];
        if (status?.edition === 'soai-core' && status.declaration === 'organization_commercial') {
            flows = ['core_evaluation', 'commercial_activation'];
        } else if (status?.edition === 'soai-os' && status.declaration === 'personal') {
            flows = ['personal_os_activation'];
        } else if (status?.edition === 'soai-os' && status.declaration === 'organization_commercial') {
            flows = ['commercial_activation'];
        }
        if (flows.length === 0) throw new TypeError('Wizard product access has no valid governing-document flow');
        for (const flow of flows) {
            if (!this.#dependencies.host.view.state.legalDocumentSets.has(flow)) {
                this.#dependencies.host.view.state.legalDocumentSets.set(flow, await this.#dependencies.host.data.governingDocuments(flow));
            }
        }
        await this.#loadEditionTerms();
    }

    async handleSelection(source: HTMLInputElement): Promise<void> {
        const selectionRevision = this.#selectionRevision + 1;
        this.#selectionRevision = selectionRevision;
        const selected = readProductAccessFlow(source.value);
        if (selected === null) throw new TypeError('Wizard product access selection is invalid');
        const ui = this.#dependencies.host.view.requireUi();
        const status = this.#dependencies.host.view.state.status;
        const operation = status?.operation ?? null;
        const operationInProgress = operation !== null && isLicensingOperationInProgress(operation.state);
        if (operationInProgress && status?.selectedProductAccessFlow !== selected) {
            const confirmed = await requireDialogsService().showConfirmation({
                title: i18n.t('wizard.productAccess.operation.switchWarning'),
                message: i18n.t('wizard.productAccess.operation.switchWarning'),
                confirmText: i18n.t('common.confirm'),
                variant: 'warning',
                confirmVariant: 'ui-variant-accent'
            });
            if (selectionRevision !== this.#selectionRevision) return;
            if (!confirmed) {
                this.#dependencies.host.view.syncProductAccessSelection(ui, status?.selectedProductAccessFlow ?? null, false);
                return;
            }
        }
        this.#dependencies.clearSensitiveInput();
        this.#dependencies.clearInlineError();
        this.#dependencies.host.view.syncProductAccessSelection(ui, selected, true);
    }

    async #loadEditionTerms(): Promise<void> {
        const status = this.#dependencies.host.view.state.status;
        if (status?.edition === 'soai-core' && status.declaration === 'organization_commercial' && this.#dependencies.host.view.state.evaluationTerms === null) {
            const document = await this.#dependencies.host.data.evaluationTerms();
            const governingDocument = this.#dependencies.host.view.state.legalDocumentSets.get('core_evaluation')?.documents.find((candidate) => candidate.documentId === 'organization_evaluation_terms');
            if (document.edition !== status.edition || document.fingerprint !== status.evaluationTerms?.fingerprint || document.fingerprint !== governingDocument?.fingerprint || document.licenseText !== governingDocument?.licenseText) throw new TypeError('Evaluation terms do not match wizard status and governing documents.');
            this.#dependencies.host.view.state.evaluationTerms = document;
        }
        if (status?.edition === 'soai-os' && status.declaration === 'personal' && this.#dependencies.host.view.state.personalPurchaseTerms === null) {
            const document = await this.#dependencies.host.data.personalPurchaseTerms();
            const governingDocument = this.#dependencies.host.view.state.legalDocumentSets.get('personal_os_activation')?.documents.find((candidate) => candidate.documentId === 'personal_os_purchase_terms');
            if (document.edition !== status.edition || document.fingerprint !== status.personalPurchaseTerms?.fingerprint || document.fingerprint !== governingDocument?.fingerprint || document.licenseText !== governingDocument?.licenseText) throw new TypeError('Personal purchase terms do not match wizard status and governing documents.');
            this.#dependencies.host.view.state.personalPurchaseTerms = document;
        }
    }
}

export { WizardProductAccessController };
