/* SoAI - Model detail view ownership [frontend/assets/ts/pages/modeldetail/controllers/page/ModelDetailViewController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { setOpenAICapabilityControlsBusy } from '@features/models/public.ts';
import type { ParametersData } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import { getModelDetailDisplayName, getModelDetailSourceModelId, setModelDetailInfo, updateModelDetailHeaderInfo } from '@pages/modeldetail/controllers/page/state.ts';
import type { ModelDetailViewHost } from '@pages/modeldetail/controllers/page/view/types.ts';
import { populateModelDetailCards, populateModelDetailModelInformation, updateModelDetailBackendDocButtonVisibility } from '@pages/modeldetail/controllers/page/view/service.ts';
import type { ParameterStateManager } from '@pages/modeldetail/controllers/ParameterStateManager.ts';
import type { ParameterViewManager } from '@pages/modeldetail/controllers/ParameterViewManager.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { ModelDetailSaveStatusState } from '@pages/modeldetail/state/ModelDetailSaveStatusState.ts';

interface ModelDetailViewControllerDependencies {
    session: ModelDetailSession;
    pageDom: PageDom;
    view: ModelDetailViewHost;
    parameterState: ParameterStateManager;
    parameterView: ParameterViewManager;
    saveStatus: ModelDetailSaveStatusState;
}

class ModelDetailViewController {
    readonly #dependencies: ModelDetailViewControllerDependencies;

    constructor(dependencies: ModelDetailViewControllerDependencies) {
        this.#dependencies = dependencies;
    }

    applyParametersPayload(payload: ParametersData = {}): void {
        const dependencies = this.#dependencies;
        dependencies.session.parameters = payload;
        dependencies.parameterState.applyPayload(payload);
        dependencies.parameterView.handleParametersApplied();
        this.populateDetailCards();
    }

    setInfo(id: string, value: JsonValue | null | undefined, format: (input: JsonValue | null | undefined) => string | null = (input) => (isNullOrUndefined(input) || input === '' ? null : String(input))): void {
        setModelDetailInfo({ pageDom: this.#dependencies.pageDom }, id, value, format);
    }

    updateHeaderInfo(): void {
        const { pageDom, session } = this.#dependencies;
        updateModelDetailHeaderInfo({
            pageDom,
            model: session.model,
            pluginCollectionSnapshot: session.pluginSnapshot,
            getModelDisplayName: () => getModelDetailDisplayName(session.model),
            getModelSourceModelId: () => getModelDetailSourceModelId(session.model)
        });
    }

    populateModelInfo(): void {
        populateModelDetailModelInformation(this.#dependencies.view);
    }

    populateDetailCards(): void {
        const dependencies = this.#dependencies;
        populateModelDetailCards(dependencies.view);
        if (dependencies.session.ui) {
            setOpenAICapabilityControlsBusy(dependencies.session.ui.root, dependencies.saveStatus.busy);
        }
    }

    updateBackendDocButtonVisibility(): void {
        updateModelDetailBackendDocButtonVisibility(this.#dependencies.view);
    }

    renderParametersInterface(): void {
        const dependencies = this.#dependencies;
        dependencies.parameterView.renderInterface(dependencies.session.model?.type === 'virtual', dependencies.session.model);
    }
}

export { ModelDetailViewController };
export type { ModelDetailViewControllerDependencies };
