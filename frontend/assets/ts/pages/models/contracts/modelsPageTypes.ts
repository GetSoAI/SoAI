/* SoAI - Models page types [frontend/assets/ts/pages/models/contracts/modelsPageTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/contracts.ts';

type Sanitizer = Pick<SanitizerApi, 'attribute' | 'html' | 'text'>;

export type { Sanitizer };
