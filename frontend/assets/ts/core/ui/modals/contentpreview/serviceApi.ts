/* SoAI - Shared UI service API [frontend/assets/ts/core/ui/modals/contentpreview/serviceApi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { ContentPreviewImageNavigationDirection, ContentPreviewMediaRequest, ContentPreviewTextDraftSnapshot, ContentPreviewOpenRequest } from '@core/ui/modals/contentpreview/types.ts';

type ContentPreviewServiceApi = {
    open: (request: ContentPreviewOpenRequest) => void;
    completeImageNavigation: (request: ContentPreviewMediaRequest, direction: ContentPreviewImageNavigationDirection) => Promise<boolean>;
    close: () => void;
    isOpen: () => boolean;
    isEditing: () => boolean;
    enterEditMode: () => void;
    exitEditMode: () => void;
    hasTextDraftChanges: () => boolean;
    getTextDraftSnapshot: () => ContentPreviewTextDraftSnapshot | null;
    requestSave: () => Promise<void>;
    setTextSelectedColor: (color: string | null) => void;
};

const isContentPreviewServiceApi = <T>(value: T): value is T & ContentPreviewServiceApi => {
    if (!isObject(value)) {
        return false;
    }
    return hasFunctionProperty(value, 'open') && hasFunctionProperty(value, 'completeImageNavigation') && hasFunctionProperty(value, 'close') && hasFunctionProperty(value, 'isOpen') && hasFunctionProperty(value, 'isEditing') && hasFunctionProperty(value, 'enterEditMode') && hasFunctionProperty(value, 'exitEditMode') && hasFunctionProperty(value, 'hasTextDraftChanges') && hasFunctionProperty(value, 'getTextDraftSnapshot') && hasFunctionProperty(value, 'requestSave') && hasFunctionProperty(value, 'setTextSelectedColor');
};

export { isContentPreviewServiceApi };
export type { ContentPreviewServiceApi };
