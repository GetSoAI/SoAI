/* SoAI - Hardware feature privacy install paths [frontend/assets/ts/features/hardware/privacyInstallPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ProtectedInstallPaths {
    text: string;
    paths: string[];
}

const SOAI_INSTALL_PATH_PATTERN = /(?:[A-Za-z]:\\(?:[^\\\s:)]+\\)*soai(?:\\[^\s:)]*)*|\\\\[^\\\s:)]+\\(?:[^\\\s:)]+\\)*soai(?:\\[^\s:)]*)*|(?:\/[^/\s:)]+)*\/soai(?:\/[^\s:)]*)*)/gi;

const protectSoAIInstallPaths = (text: string): ProtectedInstallPaths => {
    const paths: string[] = [];
    const protectedText = text.replace(SOAI_INSTALL_PATH_PATTERN, (match) => {
        const placeholder = `__SOAI_INSTALL_PATH_${paths.length}__`;
        paths.push(match);
        return placeholder;
    });
    return { text: protectedText, paths };
};

const restoreSoAIInstallPaths = (text: string, paths: readonly string[]): string => {
    let restoredText = text;
    paths.forEach((path, index) => {
        restoredText = restoredText.replace(`__SOAI_INSTALL_PATH_${index}__`, path);
    });
    return restoredText;
};

const isSoAIInstallPath = (path: string): boolean => {
    SOAI_INSTALL_PATH_PATTERN.lastIndex = 0;
    const isInstallPath = SOAI_INSTALL_PATH_PATTERN.test(path);
    SOAI_INSTALL_PATH_PATTERN.lastIndex = 0;
    return isInstallPath;
};

export { isSoAIInstallPath, protectSoAIInstallPaths, restoreSoAIInstallPaths };
export type { ProtectedInstallPaths };
