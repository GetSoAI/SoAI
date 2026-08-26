/* SoAI - File Explorer breadcrumb rendering [frontend/assets/ts/pages/fileexplorer/rendering/FileExplorerBreadcrumbWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { joinVirtualPath, toVirtualPath } from '@core/fileexplorerbrowser/paths.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderLabelAttributes, type TrustedHtml } from '@core/security/public.ts';
import { joinUiHtml, uiAttr, uiHtml, uiText } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { FILE_EXPLORER_ACTION_NAVIGATE_PATH, FILE_EXPLORER_ACTION_PATH_EDIT_START } from '@features/fileexplorer/public.ts';

interface FileExplorerBreadcrumbSegment {
    label: string;
    path: string;
}

interface FileExplorerBreadcrumbOptions {
    virtualPath: string;
    displayPath: string;
    workspaceRootLabel: string;
}

interface FileExplorerBreadcrumbWidgetDependencies {
    container: HTMLElement;
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
}

const buildBreadcrumbSegments = (virtualPath: string, workspaceRootLabel: string): readonly FileExplorerBreadcrumbSegment[] => {
    const segments: FileExplorerBreadcrumbSegment[] = [{ label: workspaceRootLabel, path: '/' }];
    let cumulativePath = '/';
    for (const name of toVirtualPath(virtualPath).split('/')) {
        if (!name) {
            continue;
        }
        cumulativePath = joinVirtualPath(cumulativePath, name);
        segments.push({ label: name, path: cumulativePath });
    }
    return segments;
};

const renderBreadcrumbSegment = (segment: FileExplorerBreadcrumbSegment, isLast: boolean): TrustedHtml => {
    const classValue = `ui-button-quiet file-explorer-breadcrumb__crumb${isLast ? ' file-explorer-breadcrumb__crumb--current' : ''}`;
    return uiHtml`<button type="button" class="${uiAttr(classValue)}" data-action="${uiAttr(FILE_EXPLORER_ACTION_NAVIGATE_PATH)}" data-path="${uiAttr(segment.path)}"${renderLabelAttributes(segment.label)}>${uiText(segment.label)}</button>`;
};

class FileExplorerBreadcrumbWidget {
    readonly #container: HTMLElement;
    readonly #getIconSync: FileExplorerBreadcrumbWidgetDependencies['getIconSync'];
    readonly #resizeObserver: ResizeObserver;
    #disposed = false;

    constructor(dependencies: FileExplorerBreadcrumbWidgetDependencies) {
        this.#container = dependencies.container;
        this.#getIconSync = dependencies.getIconSync;
        const ResizeObserverConstructor = dependencies.container.ownerDocument.defaultView?.ResizeObserver;
        if (typeof ResizeObserverConstructor !== 'function') {
            throw new Error('File Explorer breadcrumb requires ResizeObserver');
        }
        this.#resizeObserver = new ResizeObserverConstructor(() => {
            if (!this.#disposed) this.#updateOverflow();
        });
        this.#resizeObserver.observe(this.#container);
    }

    render(options: FileExplorerBreadcrumbOptions): void {
        if (this.#disposed) {
            throw new Error('Cannot render a disposed File Explorer breadcrumb');
        }
        const segments = buildBreadcrumbSegments(options.virtualPath, options.workspaceRootLabel);
        const separatorIcon = this.#getIconSync('chevron-right', { size: 14, strokeWidth: 2 });
        const rootIcon = this.#getIconSync('folder', { size: 15, strokeWidth: 1.5 });
        const crumbs = segments.map((segment, index) => {
            const separator = index === 0 ? uiHtml`` : uiHtml`<span class="file-explorer-breadcrumb__separator" aria-hidden="true">${renderIconSlot(separatorIcon)}</span>`;
            return uiHtml`<span class="file-explorer-breadcrumb__segment">${separator}${renderBreadcrumbSegment(segment, index === segments.length - 1)}</span>`;
        });
        const editLabel = i18n.t('fileExplorer.actions.editPath');
        const markup = uiHtml`<span class="file-explorer-breadcrumb__root-icon" aria-hidden="true">${renderIconSlot(rootIcon)}</span><span class="file-explorer-breadcrumb__ellipsis" aria-hidden="true" hidden>…</span>${joinUiHtml(crumbs)}<button type="button" class="file-explorer-breadcrumb__tail" data-action="${uiAttr(FILE_EXPLORER_ACTION_PATH_EDIT_START)}"${renderLabelAttributes(editLabel)}></button>`;
        dom.setHTML(this.#container, markup, { escape: false });
        this.#container.dataset['currentPath'] = options.displayPath;
        this.#updateOverflow();
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#resizeObserver.disconnect();
    }

    #updateOverflow(): void {
        const segments = dom.resolveAll('.file-explorer-breadcrumb__segment', this.#container).filter((element): element is HTMLElement => element instanceof HTMLElement);
        const ellipsis = dom.resolve('.file-explorer-breadcrumb__ellipsis', this.#container);
        if (!(ellipsis instanceof HTMLElement)) return;
        this.#container.classList.remove('file-explorer-breadcrumb--truncate-current');
        for (const segment of segments) segment.hidden = false;
        ellipsis.hidden = true;
        if (this.#container.scrollWidth <= this.#container.clientWidth) return;
        if (segments.length < 2) {
            this.#container.classList.add('file-explorer-breadcrumb--truncate-current');
            return;
        }
        ellipsis.hidden = false;
        for (const segment of segments.slice(0, -1)) {
            segment.hidden = true;
            if (this.#container.scrollWidth <= this.#container.clientWidth) return;
        }
        this.#container.classList.add('file-explorer-breadcrumb--truncate-current');
    }
}

export { FileExplorerBreadcrumbWidget };
export type { FileExplorerBreadcrumbOptions, FileExplorerBreadcrumbWidgetDependencies };
