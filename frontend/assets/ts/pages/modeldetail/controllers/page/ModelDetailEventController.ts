/* SoAI - Model detail event ownership [frontend/assets/ts/pages/modeldetail/controllers/page/ModelDetailEventController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { SaveController } from '@core/save/public.ts';
import { setOpenAICapabilityControlsBusy } from '@features/models/public.ts';
import { isModeldetailActionId } from '@pages/modeldetail/actions.ts';
import type { ModelDetailActionsHost } from '@pages/modeldetail/controllers/page/actionEffects.ts';
import { dispatchModelDetailDelegatedAction, handleModelDetailDelegatedChange, handleModelDetailDelegatedClick } from '@pages/modeldetail/controllers/page/delegatedActionsController.ts';
import { bindModelDetailAuxEventListeners, createModelDetailDelegatedActionHandlers, type ModelDetailEventDependencies } from '@pages/modeldetail/controllers/page/eventListeners.ts';
import type { ModelDetailOperationsHost } from '@pages/modeldetail/controllers/page/operations/types.ts';
import type { ModelDetailViewHost } from '@pages/modeldetail/controllers/page/view/types.ts';
import type { TestModalManager } from '@features/modeldetail/public.ts';
import type { ModelDetailUi } from '@pages/modeldetail/dom.ts';
import type { ModelDetailSession } from '@pages/modeldetail/state/ModelDetailSession.ts';
import type { ModelDetailLanguageChangedDependencies } from '@pages/modeldetail/controllers/page/dom.ts';
import type { ModelDetailSaveStatusState } from '@pages/modeldetail/state/ModelDetailSaveStatusState.ts';

interface ModelDetailEventControllerDependencies {
    session: ModelDetailSession;
    pageLifecycle: PageLifecycle;
    events: ModelDetailEventDependencies & ModelDetailLanguageChangedDependencies;
    view: ModelDetailViewHost;
    actions: ModelDetailActionsHost;
    operations: ModelDetailOperationsHost;
    save: SaveController;
    saveStatus: ModelDetailSaveStatusState;
    testModalManager: TestModalManager;
    ensureUi(): ModelDetailUi;
}

class ModelDetailEventController {
    readonly #dependencies: ModelDetailEventControllerDependencies;
    readonly #handleTestModalClose = (): void => {
        this.#dependencies.testModalManager.resetModal();
    };

    constructor(dependencies: ModelDetailEventControllerDependencies) {
        this.#dependencies = dependencies;
    }

    bind(): void {
        const dependencies = this.#dependencies;
        const ui = dependencies.ensureUi();
        const signal = dependencies.pageLifecycle.beginListeners();
        dependencies.session.listeners = dependencies.pageLifecycle.listenersController;
        ui.modelTestModal.addEventListener('core.modal.close', this.#handleTestModalClose, { signal });
        dependencies.save.attach({
            resolveSaveButtons: () => [ui.saveParametersHeaderButton, ui.openAICapabilitiesSaveButton],
            autoNotifyRoot: ui.root,
            onBusyChange: (busy) => {
                dependencies.saveStatus.update(busy);
                setOpenAICapabilityControlsBusy(ui.root, busy);
            },
            buttonDirtyClassName: 'ui-button-glow'
        });
        const handlers = createModelDetailDelegatedActionHandlers({
            host: dependencies.events,
            view: dependencies.view,
            actionsHost: dependencies.actions,
            operationsHost: dependencies.operations,
            save: dependencies.save
        });
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'ModelDetailPage',
            isAction: isModeldetailActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }) => handleModelDetailDelegatedClick({ event, action, actionElement, handlers })
                },
                change: {
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }) => handleModelDetailDelegatedChange({ event, action, actionElement, handlers })
                }
            }
        });
        bindPageActionDispatcher({
            root: ui.modelTestModal,
            signal,
            label: 'ModelDetailPage test modal',
            isAction: isModeldetailActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }) => dispatchModelDetailDelegatedAction({ event, action, actionElement, handlers })
                }
            }
        });
        bindModelDetailAuxEventListeners({ host: dependencies.events, session: dependencies.session, ui, signal });
    }
}

export { ModelDetailEventController };
export type { ModelDetailEventControllerDependencies };
