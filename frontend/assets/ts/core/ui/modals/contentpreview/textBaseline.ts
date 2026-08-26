/* SoAI - Shared UI text baseline [frontend/assets/ts/core/ui/modals/contentpreview/textBaseline.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';
import type { ContentPreviewTextBaseline } from '@core/ui/modals/contentpreview/types.ts';

const normalizeContentPreviewTextBaseline = (baseline: ContentPreviewTextBaseline): ContentPreviewTextBaseline =>
    Object.freeze({
        title: isString(baseline.title) ? baseline.title : '',
        content: isString(baseline.content) ? baseline.content : '',
        promptColor: baseline.promptColor ? String(baseline.promptColor) : null
    });

const createEmptyContentPreviewTextBaseline = (): ContentPreviewTextBaseline =>
    normalizeContentPreviewTextBaseline(
        Object.freeze({
            title: '',
            content: '',
            promptColor: null
        })
    );

export { createEmptyContentPreviewTextBaseline, normalizeContentPreviewTextBaseline };
