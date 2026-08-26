/* SoAI - Shared UI external open [frontend/assets/ts/core/ui/modals/contentpreview/externalOpen.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getLocation } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { ContentPreviewExternalOpenBehavior, ContentPreviewScope } from '@core/ui/modals/contentpreview/types.ts';

const resolveExternal = (url: string): boolean => {
    const trimmed = url.trim();
    if (!trimmed) {
        return false;
    }
    if (trimmed.startsWith('/')) {
        return false;
    }
    const location = getLocation();
    try {
        const resolved = new URL(trimmed, location.href);
        return resolved.origin !== location.origin;
    } catch (error) {
        errorHandler.debug('ContentPreviewModal', 'Failed to parse external open URL', ensureError(error));
        return true;
    }
};

const maybeConfirmExternalOpen = async (inputArguments: { scope: ContentPreviewScope; behavior: ContentPreviewExternalOpenBehavior; url: string }): Promise<boolean> => {
    const dialogsService = requireDialogsService();
    const behavior = inputArguments.behavior;
    if (behavior === 'neverConfirm') {
        return true;
    }
    if (behavior === 'alwaysConfirm') {
        if (inputArguments.scope === 'chat') {
            return await dialogsService.showChatExternalLinkModal({ url: inputArguments.url });
        }
        return await dialogsService.showExternalLinkModal({ url: inputArguments.url });
    }
    if (!resolveExternal(inputArguments.url)) {
        return true;
    }
    if (inputArguments.scope === 'chat') {
        return await dialogsService.showChatExternalLinkModal({ url: inputArguments.url });
    }
    return await dialogsService.showExternalLinkModal({ url: inputArguments.url });
};

export { maybeConfirmExternalOpen };
