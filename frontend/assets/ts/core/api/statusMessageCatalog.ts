/* SoAI - Shared API status message catalog [frontend/assets/ts/core/api/statusMessageCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ApiStatusMessageKeys } from '@core/api/httpStatusNotifications.ts';

const FILE_EXPLORER_HTTP_STATUS_MESSAGES: ApiStatusMessageKeys = {
    forbidden: (): string => i18n.t('fileExplorer.errors.http.403'),
    missing: (): string => i18n.t('fileExplorer.errors.http.404'),
    precondition: (): string => i18n.t('fileExplorer.errors.http.412')
};

export { FILE_EXPLORER_HTTP_STATUS_MESSAGES };
