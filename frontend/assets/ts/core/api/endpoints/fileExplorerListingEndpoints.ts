/* SoAI - Shared frontend API endpoint layer file explorer listing endpoints [frontend/assets/ts/core/api/endpoints/fileExplorerListingEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeFileExplorerListingAcceptedResponse, decodeFileExplorerListingLocateResponse, decodeFileExplorerListingPageResponse, decodeFileExplorerListingReleasedResponse, serializeFileExplorerListingLocateQuery, serializeFileExplorerListingPageQuery, serializeFileExplorerListingStartRequest } from '@core/api/contracts/fileExplorerListingContracts.ts';
import type { FileExplorerListingAcceptedResponse, FileExplorerListingLocateOptions, FileExplorerListingLocateResponse, FileExplorerListingPageOptions, FileExplorerListingPageResponse, FileExplorerListingReleasedResponse } from '@core/api/contracts/fileExplorerListingContractTypes.ts';
import { FILE_EXPLORER_BASE_PATH } from '@core/api/endpoints/fileExplorerPaths.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { buildSignalRequestOptions, requireNonEmptyRequestString } from '@core/api/requestOptions.ts';

interface FileExplorerListingEndpoints {
    startListing(listingId: string, path: string, signal?: AbortSignal): Promise<FileExplorerListingAcceptedResponse>;
    getListingPage(listingId: string, options: FileExplorerListingPageOptions): Promise<FileExplorerListingPageResponse>;
    locateListingEntry(listingId: string, name: string, options: FileExplorerListingLocateOptions): Promise<FileExplorerListingLocateResponse>;
    releaseListing(listingId: string, signal?: AbortSignal): Promise<FileExplorerListingReleasedResponse>;
}

const LISTING_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

const requireListingIdentity = <Response extends { listingId: string }>(response: Response, listingId: string): Response => {
    if (response.listingId !== listingId) throw new TypeError('File explorer response has an unexpected listing identity');
    return response;
};

const createFileExplorerListingEndpoints = (api: ApiClientContext): FileExplorerListingEndpoints => {
    const requireValue = (value: string, field: string): string => requireNonEmptyRequestString(value, field, 'fileExplorer');
    const requireListingId = (value: string, field: string): string => {
        const listingId = requireValue(value, field);
        if (!LISTING_ID_PATTERN.test(listingId)) throw new TypeError(`fileExplorer ${field} is invalid`);
        return listingId;
    };
    return {
        startListing: async (listingId: string, path: string, signal?: AbortSignal): Promise<FileExplorerListingAcceptedResponse> => {
            const validatedListingId = requireListingId(listingId, 'startListing.listingId');
            return requireListingIdentity(decodeFileExplorerListingAcceptedResponse(await api.post(`${FILE_EXPLORER_BASE_PATH}/listings`, serializeFileExplorerListingStartRequest(validatedListingId, requireValue(path, 'startListing.path')), signal ? { signal } : undefined)), validatedListingId);
        },
        getListingPage: async (listingId: string, options: FileExplorerListingPageOptions): Promise<FileExplorerListingPageResponse> => {
            const validatedListingId = requireListingId(listingId, 'getListingPage.listingId');
            const response = requireListingIdentity(
                decodeFileExplorerListingPageResponse(
                    await api.get(`${FILE_EXPLORER_BASE_PATH}/listings/${api.encodePathSegment(validatedListingId)}`, {
                        ...buildSignalRequestOptions(options),
                        query: serializeFileExplorerListingPageQuery(options)
                    })
                ),
                validatedListingId
            );
            if (response.offset !== options.offset || response.limit !== options.limit) {
                throw new TypeError('File explorer response has unexpected pagination coordinates');
            }
            return response;
        },
        locateListingEntry: async (listingId: string, name: string, options: FileExplorerListingLocateOptions): Promise<FileExplorerListingLocateResponse> =>
            decodeFileExplorerListingLocateResponse(
                await api.get(`${FILE_EXPLORER_BASE_PATH}/listings/${api.encodePathSegment(requireListingId(listingId, 'locateListingEntry.listingId'))}/locate`, {
                    ...buildSignalRequestOptions(options),
                    query: serializeFileExplorerListingLocateQuery(requireValue(name, 'locateListingEntry.name'), options)
                })
            ),
        releaseListing: async (listingId: string, signal?: AbortSignal): Promise<FileExplorerListingReleasedResponse> => {
            const validatedListingId = requireListingId(listingId, 'releaseListing.listingId');
            return requireListingIdentity(decodeFileExplorerListingReleasedResponse(await api.delete(`${FILE_EXPLORER_BASE_PATH}/listings/${api.encodePathSegment(validatedListingId)}`, signal ? { keepalive: true, signal } : { keepalive: true })), validatedListingId);
        }
    };
};

export { createFileExplorerListingEndpoints };
export type { FileExplorerListingEndpoints };
