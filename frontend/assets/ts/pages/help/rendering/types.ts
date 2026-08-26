/* SoAI - Help page rendering contracts [frontend/assets/ts/pages/help/rendering/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';

type GenerateStandardHeaderFunctionValue = (options: GenerateStandardHeaderOptions) => TrustedHtml;

export type { GenerateStandardHeaderFunctionValue };
