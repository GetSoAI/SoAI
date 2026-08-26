/* SoAI - Tasks feature task manager store constants [frontend/assets/ts/features/tasks/taskmanagerstore/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PLUGIN_ACTIVE_STATUSES, PLUGIN_BLOCKING_STATUSES, PLUGIN_STATUS_PERSISTENT_READY } from '@core/state/pluginStatus.ts';
import type { OperationDefinition } from '@features/tasks/taskmanager/taskManagerModels.ts';

const OPERATION_TYPE_CONFIG: Record<string, OperationDefinition> = Object.freeze({
    'plugin-download': { cancelable: true },
    'model-download': { cancelable: true },
    'backend-install': { cancelable: true },
    'backend-update': { cancelable: true },
    'backend-update-all': { cancelable: true },
    'backend-remove': { cancelable: true },
    'force-cleanup': { cancelable: true },
    'rag-document-upload': { cancelable: true },
    'rag-url-fetch': { cancelable: true },
    'rag-folder-scan': { cancelable: true },
    'rag-search': { cancelable: true },
    'web-search': { cancelable: true },
    'web-fetch': { cancelable: true },
    'software-update': { cancelable: true },
    'background-job': { cancelable: true },
    'mcp-operation': { cancelable: true },
    'plugin-clone': { cancelable: true },
    'plugin-delete': { cancelable: true },
    'plugin-upload': { cancelable: true },
    'file-explorer-op': { cancelable: true },
    'wallpaper-update': { cancelable: true },
    'model-delete': { cancelable: false },
    'backup-create': { cancelable: false },
    'backup-restore': { cancelable: false },
    'backup-verify': { cancelable: false },
    'backup-delete': { cancelable: true },
    'chat-request': { cancelable: true }
});

const ACTIVE_STATUSES: ReadonlySet<string> = PLUGIN_ACTIVE_STATUSES;
const BLOCKING_PLUGIN_STATUSES = PLUGIN_BLOCKING_STATUSES;
const PERSISTENT_STATUS = PLUGIN_STATUS_PERSISTENT_READY;
const PROGRESS_STATUSES: ReadonlySet<string> = new Set(['STARTING', 'LOADING', 'READY_PENDING_DISPATCH', 'PROCESSING']);

export { ACTIVE_STATUSES, BLOCKING_PLUGIN_STATUSES, OPERATION_TYPE_CONFIG, PERSISTENT_STATUS, PROGRESS_STATUSES };
