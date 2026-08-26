/* SoAI - Canonical WebUI username value contract [frontend/assets/ts/core/users/username.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const USERNAME_MIN_LENGTH = 3;
const USERNAME_MAX_LENGTH = 50;
const USERNAME_PATTERN = /^[A-Za-z0-9_.-]{3,50}$/;

const isCanonicalUsernameInput = (value: string): boolean => USERNAME_PATTERN.test(value);

const requireCanonicalUsername = (value: string): string => {
    if (!isCanonicalUsernameInput(value)) {
        throw new Error('Username must be 3-50 ASCII letters, numbers, dots, underscores, or hyphens.');
    }
    return value.toLowerCase();
};

export { isCanonicalUsernameInput, requireCanonicalUsername, USERNAME_MAX_LENGTH, USERNAME_MIN_LENGTH, USERNAME_PATTERN };
