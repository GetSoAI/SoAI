/* SoAI - Shared models glass parts [frontend/assets/ts/core/models/requestdistributionglass/glassParts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestDistributionDataset } from '@core/models/requestDistribution.ts';
import type { TrustedHtml } from '@core/security/public.ts';

interface RequestDistributionGlassInput {
    width: number;
    height: number;
    dataset: RequestDistributionDataset;
    colors: readonly string[];
}

interface RequestDistributionGlassParts {
    defs: TrustedHtml;
    bodies: TrustedHtml;
    rims: TrustedHtml;
}

export type { RequestDistributionGlassInput, RequestDistributionGlassParts };
