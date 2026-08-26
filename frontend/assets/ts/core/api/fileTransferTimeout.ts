/* SoAI - Shared API file transfer timeout [frontend/assets/ts/core/api/fileTransferTimeout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { daysToMs } from '@core/time/durations.ts';

const FILE_TRANSFER_REQUEST_TIMEOUT_MS = daysToMs(1);

export { FILE_TRANSFER_REQUEST_TIMEOUT_MS };
