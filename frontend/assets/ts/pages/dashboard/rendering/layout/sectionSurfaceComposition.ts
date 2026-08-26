/* SoAI - Dashboard scalable section surface rendering [frontend/assets/ts/pages/dashboard/rendering/layout/sectionSurfaceComposition.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CreateSectionOptions } from '@core/routing/pages/pagetypes/public.ts';

interface DashboardSectionSurfaceHost {
    createSection: (id: string, options?: CreateSectionOptions) => HTMLElement;
    createElement: (tag: 'div', attributes: { className: string }) => HTMLDivElement;
    append: (target: Element, children: Node | Node[]) => void;
}

const createDashboardSectionSurface = (host: DashboardSectionSurfaceHost, id: string, options?: CreateSectionOptions): HTMLElement => {
    const section = host.createSection(id, options);
    const surface = host.createElement('div', { className: 'dashboard-section-surface' });
    host.append(surface, Array.from(section.childNodes));
    host.append(section, surface);
    return section;
};

export { createDashboardSectionSurface };
