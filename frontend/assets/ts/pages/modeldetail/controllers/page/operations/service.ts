/* SoAI - Model detail page control layer operations service [frontend/assets/ts/pages/modeldetail/controllers/page/operations/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { StreamHandle } from '@pages/modeldetail/contracts/modelDetailPageSupport.ts';
import type { ModelDetailOperationsDependencies, ModelDetailOperationsHost } from '@pages/modeldetail/controllers/page/operations/types.ts';
import { getModelDetailDisplayName, getModelDetailPluginStatus } from '@pages/modeldetail/controllers/page/state.ts';

const composeModelDetailOperations = (host: ModelDetailOperationsDependencies): ModelDetailOperationsHost => {
    return {
        get activeDeletionStream(): StreamHandle | null {
            return host.session.deletionStream;
        },
        set activeDeletionStream(value: StreamHandle | null) {
            host.session.deletionStream = value;
        },
        get model(): ModelRecord | null {
            return host.session.model;
        },
        get modelId(): string | null {
            return host.session.modelId;
        },
        pageDom: host.pageDom,
        pageResources: host.pageResources,
        feedback: host.feedback,
        ensureUi: () => host.ensureUi(),
        getElement: (selector, context) => host.pageElements.getElement(selector, context),
        dom: host.dom,
        runWithBoundary: (name, functionValue) => host.pageLifecycle.run(name, functionValue),
        runPageTask: (taskKey, task, options) => host.streaming.runTask(taskKey, task, options),
        startTaskAction: (endpoint, options) => host.streaming.taskAction(endpoint, options),
        getStreamTracker: (key) => host.streaming.tracker(key),
        getModelDisplayName: (): string => getModelDetailDisplayName(host.session.model),
        getPluginStatus: (): string | null => getModelDetailPluginStatus(host.session.model),
        requireModelId: () => host.requireModelId(),
        isVirtualModel: () => host.isVirtualModel(),
        api: host.api,
        get router() {
            if (!host.router) {
                throw new Error('ModelDetailPage requires router for navigation');
            }
            return host.router;
        }
    };
};

export { composeModelDetailOperations };
