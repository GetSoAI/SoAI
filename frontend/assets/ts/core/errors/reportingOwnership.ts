/* SoAI - Shared errors reporting ownership [frontend/assets/ts/core/errors/reportingOwnership.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const reportedErrors = new WeakSet<Error>();

const claimErrorReporting = (error: Error): boolean => {
    if (reportedErrors.has(error)) {
        return false;
    }
    reportedErrors.add(error);
    return true;
};

export { claimErrorReporting };
