/* SoAI - Content preview image viewer metadata state [frontend/assets/ts/core/ui/modals/contentpreview/imageViewerMetadataState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { loadContentPreviewImageMetadata, resolveContentPreviewImageFormatLabel, resolveContentPreviewImageSizeLabel } from '@core/ui/modals/contentpreview/imageViewerMetadata.ts';
import type { ContentPreviewImageViewerRefs } from '@core/ui/modals/contentpreview/imageViewerDom.ts';
import type { ContentPreviewImageMetadata } from '@core/ui/modals/contentpreview/types.ts';

type MountArguments = Readonly<{
    refs: ContentPreviewImageViewerRefs;
    sourceUrl: string;
    imageMetadata: ContentPreviewImageMetadata | null;
    metadataAbort: AbortController | null;
    setMetadataAbort: (controller: AbortController | null) => void;
    handleMetadataReady: () => void;
}>;

const applyContentPreviewImageViewerMetadata = ({ refs, sourceUrl, imageMetadata, metadataAbort, setMetadataAbort, handleMetadataReady }: MountArguments): void => {
    metadataAbort?.abort();
    if (imageMetadata) {
        refs.format.value.textContent = resolveContentPreviewImageFormatLabel(imageMetadata.contentType, sourceUrl);
        refs.size.value.textContent = resolveContentPreviewImageSizeLabel(imageMetadata.contentLength);
        setMetadataAbort(null);
        handleMetadataReady();
        return;
    }

    const nextAbort = new AbortController();
    setMetadataAbort(nextAbort);
    terminateHandledPromise(
        (async () => {
            const metadata = await loadContentPreviewImageMetadata(sourceUrl, nextAbort.signal);
            if (nextAbort.signal.aborted) {
                return;
            }
            refs.format.value.textContent = resolveContentPreviewImageFormatLabel(metadata.contentType, sourceUrl);
            refs.size.value.textContent = resolveContentPreviewImageSizeLabel(metadata.contentLength);
            setMetadataAbort(null);
            handleMetadataReady();
        })()
    );
};

export { applyContentPreviewImageViewerMetadata };
