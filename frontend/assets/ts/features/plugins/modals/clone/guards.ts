/* SoAI - Plugins feature clone validation [frontend/assets/ts/features/plugins/modals/clone/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasFunctionProperty, isPlainObject } from '@core/typeGuards.ts';
import type { CloneProgressReporter } from '@features/plugins/modals/clone/types.ts';

const isCloneProgressReporter = <T>(value: T): value is T & CloneProgressReporter => isPlainObject(value) && hasFunctionProperty(value, 'update') && hasFunctionProperty(value, 'remove') && hasFunctionProperty(value, 'clear') && hasFunctionProperty(value, 'destroy') && hasFunctionProperty(value, 'hasActiveOperations');

export { isCloneProgressReporter };
