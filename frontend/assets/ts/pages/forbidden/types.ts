/* SoAI - Forbidden page contracts [frontend/assets/ts/pages/forbidden/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';

type GenerateStandardHeaderFunctionValue = (options: GenerateStandardHeaderOptions) => TrustedHtml;
type GetIconSyncFunctionValue = (name: IconName, options?: IconOptions) => TrustedHtml;

interface ForbiddenViewDependencies {
    generateStandardHeader: GenerateStandardHeaderFunctionValue;
    getIconSync: GetIconSyncFunctionValue;
    requestedPageTitle: string | null;
}

export type { ForbiddenViewDependencies };
