/* SoAI - Plugins feature concurrent manager validation [frontend/assets/ts/features/plugins/modals/concurrentmanager/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isObject } from '@core/typeGuards.ts';
import type { ConcurrentRestartOperationType } from '@features/plugins/modals/concurrentmanager/types.ts';

const isOverlayWithShow = <T>(value: T): value is T & { show: (type: ConcurrentRestartOperationType) => void } => isObject(value) && hasFunctionProperty(value, 'show');

export { isOverlayWithShow };
