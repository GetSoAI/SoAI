/* SoAI - Content preview image viewer DOM [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerDom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { CONTENT_PREVIEW_ACTION_ATTR, CONTENT_PREVIEW_ACTIONS, type ContentPreviewAction } from '@core/ui/modals/contentpreview/constants.ts';
import { appendContentPreviewSourceReferenceMetric, type ContentPreviewSourceReferenceMetric } from '@core/ui/modals/contentpreview/sourceReference.ts';
import type { ContentPreviewImageNavigation, ContentPreviewSourceReference } from '@core/ui/modals/contentpreview/types.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

type ContentPreviewImageViewerInfoItem = Readonly<{
    value: HTMLElement;
}>;

type ContentPreviewImageViewerRefs = Readonly<{
    viewer: HTMLDivElement;
    viewport: HTMLDivElement;
    scene: HTMLDivElement;
    stage: HTMLDivElement;
    image: HTMLImageElement;
    loadingOverlay: HTMLDivElement;
    minimap: HTMLDivElement;
    minimapImage: HTMLImageElement;
    minimapFrame: HTMLDivElement;
    minimapViewport: HTMLDivElement;
    minimapZoom: HTMLDivElement;
    info: HTMLDivElement;
    metadata: HTMLDivElement;
    metadataItems: HTMLDListElement;
    loadingStatus: HTMLDivElement;
    loadingPath: HTMLSpanElement;
    sourceReference: ContentPreviewSourceReferenceMetric | null;
    position: HTMLSpanElement;
    previousButton: HTMLButtonElement | null;
    nextButton: HTMLButtonElement | null;
    resolution: ContentPreviewImageViewerInfoItem;
    format: ContentPreviewImageViewerInfoItem;
    size: ContentPreviewImageViewerInfoItem;
    zoom: ContentPreviewImageViewerInfoItem;
}>;

const createInfoItem = (documentRef: Document, host: HTMLDListElement, label: string): ContentPreviewImageViewerInfoItem => {
    const item = documentRef.createElement('div');
    item.className = 'content-preview-image-info-item';

    const title = documentRef.createElement('dt');
    title.className = 'content-preview-image-info-label';
    title.textContent = label;

    const value = documentRef.createElement('dd');
    value.className = 'content-preview-image-info-value';
    value.textContent = i18n.t('common.unknown');

    item.appendChild(title);
    item.appendChild(value);
    host.appendChild(item);

    return Object.freeze({ value });
};

const createNavigationButton = (documentRef: Document, action: ContentPreviewAction, label: string, iconName: IconName): HTMLButtonElement => {
    const button = documentRef.createElement('button');
    button.type = 'button';
    button.className = 'content-preview-image-navigation-button ui-icon-button ui-variant-neutral';
    button.setAttribute(CONTENT_PREVIEW_ACTION_ATTR, action);
    button.setAttribute('aria-label', label);
    setTooltipText(button, label);
    button.appendChild(createIconSlot(documentRef, getIconSync(iconName, { size: 16, strokeWidth: 1.5 })));
    return button;
};

type ContentPreviewImageNavigationRefs = Readonly<{
    controls: HTMLDivElement;
    previousButton: HTMLButtonElement;
    nextButton: HTMLButtonElement;
}>;

const createNavigationControls = (documentRef: Document, imageNavigation: ContentPreviewImageNavigation): ContentPreviewImageNavigationRefs => {
    const controls = documentRef.createElement('div');
    controls.className = 'content-preview-image-navigation';
    const previousButton = createNavigationButton(documentRef, CONTENT_PREVIEW_ACTIONS.IMAGE_PREVIOUS, imageNavigation.previousLabel, 'chevron-left');
    const nextButton = createNavigationButton(documentRef, CONTENT_PREVIEW_ACTIONS.IMAGE_NEXT, imageNavigation.nextLabel, 'chevron-right');
    controls.appendChild(previousButton);
    controls.appendChild(nextButton);
    return Object.freeze({ controls, previousButton, nextButton });
};

const createContentPreviewImageViewerDom = (container: HTMLElement, sourceUrl: string, title: string, imageNavigation: ContentPreviewImageNavigation | null, sourceReference: ContentPreviewSourceReference | null): ContentPreviewImageViewerRefs => {
    const documentRef = dom.getDocument();

    const viewer = documentRef.createElement('div');
    viewer.className = 'content-preview-image-viewer';

    const viewport = documentRef.createElement('div');
    viewport.className = 'content-preview-image-viewport glass-surface-darker';

    const scene = documentRef.createElement('div');
    scene.className = 'content-preview-image-scene';

    const stage = documentRef.createElement('div');
    stage.className = 'content-preview-image-stage';

    const image = documentRef.createElement('img');
    image.className = 'content-preview-image';
    image.alt = title;
    image.decoding = 'async';
    image.loading = 'eager';
    image.draggable = false;
    image.src = sourceUrl;
    stage.appendChild(image);
    scene.appendChild(stage);

    const loadingOverlay = documentRef.createElement('div');
    loadingOverlay.className = 'content-preview-image-loading-overlay';
    loadingOverlay.setAttribute('aria-hidden', 'true');
    const loadingSpinner = documentRef.createElement('span');
    loadingSpinner.className = 'loading-spinner';
    loadingSpinner.setAttribute('aria-hidden', 'true');
    loadingOverlay.appendChild(loadingSpinner);

    const minimap = documentRef.createElement('div');
    minimap.className = 'content-preview-image-minimap glass-surface-medium glass-surface--rounded';
    minimap.setAttribute('aria-hidden', 'true');

    const minimapFrame = documentRef.createElement('div');
    minimapFrame.className = 'content-preview-image-minimap-frame';

    const minimapImage = documentRef.createElement('img');
    minimapImage.className = 'content-preview-image-minimap-image';
    minimapImage.alt = '';
    minimapImage.decoding = 'async';
    minimapImage.loading = 'eager';
    minimapImage.draggable = false;
    minimapImage.src = sourceUrl;

    const minimapViewport = documentRef.createElement('div');
    minimapViewport.className = 'content-preview-image-minimap-viewport';

    const minimapZoom = documentRef.createElement('div');
    minimapZoom.className = 'content-preview-image-minimap-zoom';

    minimapFrame.appendChild(minimapImage);
    minimapFrame.appendChild(minimapViewport);
    minimap.appendChild(minimapFrame);
    minimap.appendChild(minimapZoom);

    const info = documentRef.createElement('div');
    info.className = 'content-preview-image-info glass-surface-light glass-surface--rounded';

    const metadata = documentRef.createElement('div');
    metadata.className = 'content-preview-image-info-metadata';

    const metadataItems = documentRef.createElement('dl');
    metadataItems.className = 'content-preview-image-info-metadata-items';

    const sourceReferenceMetric = appendContentPreviewSourceReferenceMetric(documentRef, metadataItems, sourceReference, {
        item: 'content-preview-image-info-item',
        label: 'content-preview-image-info-label',
        value: 'content-preview-image-info-value'
    });
    const resolution = createInfoItem(documentRef, metadataItems, i18n.t('contentPreview.imageInfo.resolution'));
    const format = createInfoItem(documentRef, metadataItems, i18n.t('contentPreview.imageInfo.format'));
    const size = createInfoItem(documentRef, metadataItems, i18n.t('contentPreview.imageInfo.size'));
    const zoom = createInfoItem(documentRef, metadataItems, i18n.t('contentPreview.imageInfo.zoom'));

    const loadingStatus = documentRef.createElement('div');
    loadingStatus.className = 'content-preview-image-info-loading content-preview-image-info-item';
    loadingStatus.setAttribute('aria-live', 'polite');
    const loadingTitle = documentRef.createElement('span');
    loadingTitle.className = 'content-preview-image-info-label';
    loadingTitle.textContent = i18n.t('contentPreview.imageInfo.loading');
    const loadingPath = documentRef.createElement('span');
    loadingPath.className = 'content-preview-image-info-value';
    loadingStatus.appendChild(loadingTitle);
    loadingStatus.appendChild(loadingPath);
    metadata.appendChild(metadataItems);
    metadata.appendChild(loadingStatus);
    info.appendChild(metadata);
    const position = documentRef.createElement('span');
    position.setAttribute('aria-live', 'polite');
    position.hidden = !imageNavigation?.position;
    if (imageNavigation?.position) {
        position.textContent = i18n.t('contentPreview.imageInfo.position', imageNavigation.position);
    }
    let previousButton: HTMLButtonElement | null = null;
    let nextButton: HTMLButtonElement | null = null;
    if (imageNavigation) {
        const navigation = createNavigationControls(documentRef, imageNavigation);
        previousButton = navigation.previousButton;
        nextButton = navigation.nextButton;
        navigation.controls.insertBefore(position, navigation.previousButton);
        info.appendChild(navigation.controls);
    }

    viewport.appendChild(scene);
    viewport.appendChild(loadingOverlay);
    viewport.appendChild(minimap);
    viewer.appendChild(viewport);
    viewer.appendChild(info);
    container.appendChild(viewer);

    if (title.trim()) {
        viewer.setAttribute('aria-label', title);
    }

    return Object.freeze({
        viewer,
        viewport,
        scene,
        stage,
        image,
        loadingOverlay,
        minimap,
        minimapImage,
        minimapFrame,
        minimapViewport,
        minimapZoom,
        info,
        metadata,
        metadataItems,
        loadingStatus,
        loadingPath,
        sourceReference: sourceReferenceMetric,
        position,
        previousButton,
        nextButton,
        resolution,
        format,
        size,
        zoom
    });
};

const updateContentPreviewImageNavigation = (refs: ContentPreviewImageViewerRefs, navigation: ContentPreviewImageNavigation | null): void => {
    refs.position.hidden = !navigation?.position;
    refs.position.textContent = navigation?.position ? i18n.t('contentPreview.imageInfo.position', navigation.position) : '';
    refs.previousButton?.parentElement?.classList.toggle('u-hidden', navigation === null);
    if (navigation && refs.previousButton && refs.nextButton) {
        refs.previousButton.setAttribute('aria-label', navigation.previousLabel);
        refs.nextButton.setAttribute('aria-label', navigation.nextLabel);
        setTooltipText(refs.previousButton, navigation.previousLabel);
        setTooltipText(refs.nextButton, navigation.nextLabel);
    }
};

export { createContentPreviewImageViewerDom, updateContentPreviewImageNavigation };
export type { ContentPreviewImageViewerInfoItem, ContentPreviewImageViewerRefs };
