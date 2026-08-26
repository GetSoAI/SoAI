/* SoAI - Backend/frontend edition integrity contract [frontend/assets/ts/core/edition/backendEditionIntegrity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type SoaiEdition = 'soai-core' | 'soai-os';

let expectedBackendEdition: SoaiEdition | null = null;

class BackendEditionIntegrityError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'BackendEditionIntegrityError';
    }
}

const isBackendEditionIntegrityError = <Value>(error: Value): error is Value & BackendEditionIntegrityError => error instanceof BackendEditionIntegrityError || (error instanceof Error && error.name === 'BackendEditionIntegrityError');

const configureExpectedBackendEdition = (edition: SoaiEdition): void => {
    if (expectedBackendEdition !== null) {
        throw new Error('Expected backend edition is already configured');
    }
    expectedBackendEdition = edition;
};

const assertBackendEdition = (edition: SoaiEdition): void => {
    if (expectedBackendEdition === null) {
        throw new BackendEditionIntegrityError('Expected backend edition is not configured');
    }
    if (edition !== expectedBackendEdition) {
        throw new BackendEditionIntegrityError('Backend and frontend editions do not match');
    }
};

const getExpectedBackendEdition = (): SoaiEdition => {
    if (expectedBackendEdition === null) {
        throw new Error('Expected backend edition is not configured');
    }
    return expectedBackendEdition;
};

export { assertBackendEdition, BackendEditionIntegrityError, configureExpectedBackendEdition, getExpectedBackendEdition, isBackendEditionIntegrityError };
export type { SoaiEdition };
