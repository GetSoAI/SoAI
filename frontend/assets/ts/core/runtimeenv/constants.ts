/* SoAI - Shared runtime environment constants [frontend/assets/ts/core/runtimeenv/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LOGS_CORE } from '@core/realtime/streammanager/resources/ids.ts';

export const LOG_TAG_DETACHED = 'DetachedCoordinator';
export const SYSTEM_LOGS_CORE_STREAM: string = LOGS_CORE;

export const VALID_HOST_ID_PATTERN = /^[\w\-.:/]+$/;
export const MAX_HOST_ID_LENGTH = 128;
