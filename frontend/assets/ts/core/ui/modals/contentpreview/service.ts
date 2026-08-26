/* SoAI - Unified content preview modal service [frontend/assets/ts/core/ui/modals/contentpreview/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CONTENT_PREVIEW_SERVICE_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { createContentPreviewModalRuntime } from '@core/ui/modals/contentpreview/modalRuntime.ts';
import { isContentPreviewServiceApi, type ContentPreviewServiceApi } from '@core/ui/modals/contentpreview/serviceApi.ts';
import { getServiceContainer } from '@core/serviceContainer.ts';

const requireContentPreviewModalService = (): ContentPreviewServiceApi => {
    const candidate = getServiceContainer().get(CONTENT_PREVIEW_SERVICE_ID);
    if (!isContentPreviewServiceApi(candidate)) {
        throw new Error(`${CONTENT_PREVIEW_SERVICE_ID} service does not match ContentPreviewServiceApi`);
    }
    return candidate;
};

const createContentPreviewModalService = (): ContentPreviewServiceApi => createContentPreviewModalRuntime();

export { createContentPreviewModalService, requireContentPreviewModalService };
