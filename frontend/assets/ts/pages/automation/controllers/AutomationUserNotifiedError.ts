/* SoAI - Automation page user notified error [frontend/assets/ts/pages/automation/controllers/AutomationUserNotifiedError.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class AutomationUserNotifiedError extends Error {
    override readonly cause: Error;

    constructor(cause: Error) {
        super(cause.message);
        this.name = 'AutomationUserNotifiedError';
        this.cause = cause;
    }
}

export { AutomationUserNotifiedError };
