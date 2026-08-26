/* SoAI - Tool media payload hashing helpers [frontend/assets/ts/features/chat/toolactivity/toolMediaPayloadHash.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const hashToolMediaPayloadString = (value: string): string => {
    let hash = 5381;
    for (let index = 0; index < value.length; index += 1) {
        hash = ((hash << 5) + hash + value.charCodeAt(index)) | 0;
    }
    return String(hash >>> 0);
};

export { hashToolMediaPayloadString };
