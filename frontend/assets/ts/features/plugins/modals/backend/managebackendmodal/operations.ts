/* SoAI - Backend management modal operations [frontend/assets/ts/features/plugins/modals/backend/managebackendmodal/operations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { createTaskOperationPanel, type TaskOperationPanel } from '@core/tasks/operationpanel/service.ts';

const MANAGE_BACKEND_OPERATION_TYPES: readonly ['backend-install', 'backend-update', 'backend-remove'] = ['backend-install', 'backend-update', 'backend-remove'];

const createManageBackendOperationFilter = (pluginName: string): { types: string[]; pluginName: string } => ({
    types: [...MANAGE_BACKEND_OPERATION_TYPES],
    pluginName
});

const attachManageBackendOperationPanel = (panel: TaskOperationPanel | null, modalId: string, pluginName: string): TaskOperationPanel => {
    panel?.detach();
    const nextPanel = createTaskOperationPanel({
        container: modalUiId(modalId, 'operation-container'),
        filter: createManageBackendOperationFilter(pluginName)
    });
    nextPanel.attach();
    return nextPanel;
};

const detachManageBackendOperationPanel = (panel: TaskOperationPanel | null): TaskOperationPanel | null => {
    panel?.detach();
    return null;
};

export { attachManageBackendOperationPanel, detachManageBackendOperationPanel };
