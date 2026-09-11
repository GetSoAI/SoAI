/* SoAI - Host filesystem browser API contracts [frontend/assets/ts/core/api/contracts/hostFilesystemBrowserContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isAbsoluteFilesystemPath } from '@core/filePathResolution.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface HostFilesystemRootsResponse {
    roots: string[];
    defaultRoot: string;
}

interface HostFilesystemLocateResponse {
    rootPath: string;
    path: string;
    absolutePath: string;
}

const decodeHostFilesystemRootsResponse = (value: ApiResponsePayload): HostFilesystemRootsResponse => {
    const label = 'Host filesystem roots response';
    const record = requireRecord(value, label);
    const rootsValue = record['roots'];
    if (!Array.isArray(rootsValue) || rootsValue.length === 0 || !rootsValue.every((root) => isString(root) && Boolean(root.trim()))) {
        throw new TypeError(`${label}.roots must be a non-empty array of non-empty strings.`);
    }
    const roots = rootsValue.map((root) => String(root));
    if (roots.some((root) => !isAbsoluteFilesystemPath(root)) || new Set(roots).size !== roots.length) {
        throw new TypeError(`${label}.roots must contain unique absolute filesystem paths.`);
    }
    const defaultRoot = readRequiredTrimmedString(record, 'default_root', `${label}.default_root`);
    if (!roots.includes(defaultRoot)) throw new TypeError(`${label}.default_root must be present in roots.`);
    return { roots: [...roots], defaultRoot };
};

const decodeHostFilesystemLocateResponse = (value: ApiResponsePayload): HostFilesystemLocateResponse => {
    const label = 'Host filesystem locate response';
    const record = requireRecord(value, label);
    const rootPath = readRequiredTrimmedString(record, 'root_path', `${label}.root_path`);
    const path = readRequiredTrimmedString(record, 'path', `${label}.path`);
    const absolutePath = readRequiredTrimmedString(record, 'absolute_path', `${label}.absolute_path`);
    if (!isAbsoluteFilesystemPath(rootPath) || !isAbsoluteFilesystemPath(absolutePath) || !path.startsWith('/')) {
        throw new TypeError(`${label} paths must use absolute native roots and an absolute virtual path.`);
    }
    return { rootPath, path, absolutePath };
};

const serializeHostFilesystemLocateRequest = (path: string): JsonObject => ({ path });

export { decodeHostFilesystemLocateResponse, decodeHostFilesystemRootsResponse, serializeHostFilesystemLocateRequest };
export type { HostFilesystemLocateResponse, HostFilesystemRootsResponse };
