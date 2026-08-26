/* SoAI - Model detail page rendering layer layout public contracts [frontend/assets/ts/pages/modeldetail/rendering/layout/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { GenerateStandardHeaderOptions, HeaderActionDefinition } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';

type RowDefinition = {
    id: string;
    className?: string;
    rowClassName?: string;
    getLabel: () => string;
};

type FilterOptionDefinition = {
    value: string;
    getLabel: () => string;
};

type HeaderConfig = GenerateStandardHeaderOptions;

interface ModelDetailLayout {
    header: HeaderConfig;
    content: string;
}

type RenderModelDetailPageViewDependencies = {
    generateStandardHeader: (options: GenerateStandardHeaderOptions) => TrustedHtml;
};

export type { FilterOptionDefinition, HeaderActionDefinition, HeaderConfig, ModelDetailLayout, RenderModelDetailPageViewDependencies, RowDefinition };
