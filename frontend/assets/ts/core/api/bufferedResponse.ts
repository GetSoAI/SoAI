/* SoAI - Shared frontend API buffered response [frontend/assets/ts/core/api/bufferedResponse.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class BufferedApiResponse {
    readonly body: Blob;
    readonly headers: Headers;
    readonly status: number;
    readonly statusText: string;

    constructor(response: Response, body: Blob) {
        this.body = body;
        this.headers = new Headers(response.headers);
        this.status = response.status;
        this.statusText = response.statusText;
    }
}

export { BufferedApiResponse };
