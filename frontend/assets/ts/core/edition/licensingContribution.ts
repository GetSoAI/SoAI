/* SoAI - Frontend edition licensing presentation contract [frontend/assets/ts/core/edition/licensingContribution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface LicensingEditionContribution {
    readonly purchaseUrl: string;
    readonly contactUrl: string;
    readonly getEditionLabel: () => string;
    readonly getWelcomeHeading: () => string;
    readonly getProductLabel: () => string;
    readonly getPurchaseLabel: () => string;
    readonly getContactLabel: () => string;
    readonly getAccessSummary: () => string;
    readonly getPersonalOffer: () => Readonly<{
        badge: string;
        price: string;
        cadence: string;
        title: string;
        description: string;
        details: readonly string[];
        termsLabel: string;
    }> | null;
}

let selectedContribution: LicensingEditionContribution | null = null;

const configureLicensingEditionContribution = (contribution: LicensingEditionContribution): void => {
    if (selectedContribution !== null) throw new Error('Licensing edition contribution is already configured.');
    selectedContribution = contribution;
};

const requireLicensingEditionContribution = (): LicensingEditionContribution => {
    if (selectedContribution === null) throw new Error('Licensing edition contribution is not configured.');
    return selectedContribution;
};

export { configureLicensingEditionContribution, requireLicensingEditionContribution };
export type { LicensingEditionContribution };
