/* SoAI - Frontend detached entry [frontend/entries/detached.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import './basePath.ts';
import { startSoaiEntry } from './shared.ts';
import { CORE_FRONTEND_EDITION } from '../assets/ts/app/edition/coreFrontendEdition.ts';

terminateHandledPromise(startSoaiEntry('detached', CORE_FRONTEND_EDITION));
