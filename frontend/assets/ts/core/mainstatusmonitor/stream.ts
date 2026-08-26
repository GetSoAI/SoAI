/* SoAI - Shared main status monitor stream [frontend/assets/ts/core/mainstatusmonitor/stream.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isStreamManager } from '@core/mainstatusmonitor/guards.ts';
import type { StreamManagerInterface } from '@core/mainstatusmonitor/types.ts';
import { STATUS } from '@core/realtime/streammanager/resources/ids.ts';

const getStatusStream = (): typeof STATUS => STATUS;

const validateMainStatusStreamManager = <T>(manager: T): T & StreamManagerInterface => {
    if (!manager) {
        throw new Error('Stream manager unavailable');
    }
    if (!isStreamManager(manager)) {
        throw new Error('Stream manager is invalid');
    }
    return manager;
};

export { getStatusStream, validateMainStatusStreamManager };
