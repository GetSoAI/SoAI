/* SoAI - Trusted product dashboard introduction contract [frontend/assets/ts/features/firstrunmodals/dashboardIntroProduct.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { StructuredTextSection } from '@core/richtextrenderer/structuredSections.ts';

interface DashboardIntroProductContribution {
    prepare(options?: { signal?: AbortSignal }): Promise<boolean>;
    isAvailable(): boolean;
    createDriverSection(): StructuredTextSection;
    createUpdatesSection(): StructuredTextSection;
}

export type { DashboardIntroProductContribution };
