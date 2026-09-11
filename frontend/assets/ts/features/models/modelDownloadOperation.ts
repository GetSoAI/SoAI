/* SoAI - Models feature durable download operation identity [frontend/assets/ts/features/models/modelDownloadOperation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TaskOperationFilter } from '@core/tasks/protocols.ts';

const MODEL_DOWNLOAD_OPERATION_TYPE = 'model-download';
const MODEL_DOWNLOAD_OPERATION_TYPES = Object.freeze([MODEL_DOWNLOAD_OPERATION_TYPE]);
const MODEL_DOWNLOAD_OPERATION_FILTER: TaskOperationFilter = Object.freeze({
    types: MODEL_DOWNLOAD_OPERATION_TYPES
});

export { MODEL_DOWNLOAD_OPERATION_FILTER, MODEL_DOWNLOAD_OPERATION_TYPE, MODEL_DOWNLOAD_OPERATION_TYPES };
