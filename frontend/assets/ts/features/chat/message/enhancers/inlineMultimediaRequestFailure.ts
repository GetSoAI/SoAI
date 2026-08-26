/* SoAI - Chat feature inline multimedia request failure [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaRequestFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHttpRequestError } from '@core/api/jsonRequestGate.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { ContentPreviewReasonCode } from '@features/chat/contentPreviewContracts.ts';

type RemoteLinkPreviewFailureReason = 'upstream_not_found' | 'upstream_gone' | 'invalid_reference' | 'request_failed';

interface InlinePreviewRequestFailure {
    message: string;
    reasonCode: ContentPreviewReasonCode;
    openFilesFolderSettings: boolean;
}

const resolveInlinePreviewRequestFailure = (error: Error, options: { openFilesFolderSettingsOnForbidden?: boolean } = {}): InlinePreviewRequestFailure => {
    if (isHttpRequestError(error)) {
        if (error.status === 404) {
            return {
                message: i18n.t('chat.inlinePreviews.notFoundMessage'),
                reasonCode: 'not_found',
                openFilesFolderSettings: false
            };
        }
        if (error.status === 401 || error.status === 403) {
            return {
                message: i18n.t('chat.inlinePreviews.accessDeniedMessage'),
                reasonCode: 'access_denied',
                openFilesFolderSettings: error.status === 403 && options.openFilesFolderSettingsOnForbidden === true
            };
        }
        if (error.status === 400) {
            return {
                message: i18n.t('chat.inlinePreviews.invalidReferenceMessage'),
                reasonCode: 'invalid_reference',
                openFilesFolderSettings: false
            };
        }
    }
    return {
        message: i18n.t('chat.inlinePreviews.requestFailedMessage'),
        reasonCode: 'request_failed',
        openFilesFolderSettings: false
    };
};

const resolveAbsolutePathsPreviewFailure = (errorCode: string | null): InlinePreviewRequestFailure => {
    const code = toTrimmedString(errorCode);
    if (!code) {
        return {
            message: i18n.t('chat.inlinePreviews.unavailableMessage'),
            reasonCode: 'request_failed',
            openFilesFolderSettings: false
        };
    }
    if (code === 'not_found') {
        return {
            message: i18n.t('chat.inlinePreviews.notFoundMessage'),
            reasonCode: 'not_found',
            openFilesFolderSettings: false
        };
    }
    if (code === 'outside_root') {
        return {
            message: i18n.t('chat.inlinePreviews.accessDeniedMessage'),
            reasonCode: 'access_denied',
            openFilesFolderSettings: true
        };
    }
    if (code === 'invalid_path') {
        return {
            message: i18n.t('chat.inlinePreviews.invalidReferenceMessage'),
            reasonCode: 'invalid_reference',
            openFilesFolderSettings: false
        };
    }
    if (code === 'server_error') {
        return {
            message: i18n.t('chat.inlinePreviews.requestFailedMessage'),
            reasonCode: 'request_failed',
            openFilesFolderSettings: false
        };
    }
    return {
        message: i18n.t('chat.inlinePreviews.unavailableMessage'),
        reasonCode: 'request_failed',
        openFilesFolderSettings: false
    };
};

const resolveRemoteLinkPreviewFailureReason = (error: Error): RemoteLinkPreviewFailureReason => {
    if (!isHttpRequestError(error)) {
        return 'request_failed';
    }
    if (error.status === 404) {
        return 'upstream_not_found';
    }
    if (error.status === 410) {
        return 'upstream_gone';
    }
    if (error.status === 400 || error.status === 422) {
        return 'invalid_reference';
    }
    return 'request_failed';
};

export { resolveInlinePreviewRequestFailure, resolveAbsolutePathsPreviewFailure, resolveRemoteLinkPreviewFailureReason };
export type { InlinePreviewRequestFailure, RemoteLinkPreviewFailureReason };
