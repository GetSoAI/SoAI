/* SoAI - Model detail page rendering [frontend/assets/ts/pages/modeldetail/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { buildHeaderConfig, renderContent } from '@pages/modeldetail/rendering/layout/service.ts';
import type { ModelDetailLayout, RenderModelDetailPageViewDependencies } from '@pages/modeldetail/rendering/layout/types.ts';

const buildModelDetailLayout = (): ModelDetailLayout => ({
    header: buildHeaderConfig(),
    content: renderContent()
});

const renderModelDetailPageView = (dependencies: RenderModelDetailPageViewDependencies): TrustedHtml => {
    const layout = buildModelDetailLayout();
    const header = dependencies.generateStandardHeader(layout.header);
    return toTrustedUiHtml(header.html.replace('<!-- Page content goes here -->', layout.content));
};

export { buildModelDetailLayout, renderModelDetailPageView };
