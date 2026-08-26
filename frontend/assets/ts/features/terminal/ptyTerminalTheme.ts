/* SoAI - PTY terminal theme [frontend/assets/ts/features/terminal/ptyTerminalTheme.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ITheme } from '@xterm/xterm';

const buildTerminalTheme = (): ITheme => {
    const style = getComputedStyle(document.documentElement);
    const resolveColor = (name: string, fallback: string): string => style.getPropertyValue(name).trim() || fallback;
    return {
        background: resolveColor('--terminal-surface', '#000000'),
        foreground: resolveColor('--terminal-foreground', '#ffffff'),
        cursor: resolveColor('--terminal-cursor', '#ffffff'),
        cursorAccent: resolveColor('--terminal-surface', '#000000'),
        selectionBackground: 'rgba(255, 255, 255, 0.3)',
        black: resolveColor('--terminal-ansi-black', '#000000'),
        red: resolveColor('--terminal-ansi-red', '#cd0000'),
        green: resolveColor('--terminal-ansi-green', '#00cd00'),
        yellow: resolveColor('--terminal-ansi-yellow', '#cdcd00'),
        blue: resolveColor('--terminal-ansi-blue', '#0000ee'),
        magenta: resolveColor('--terminal-ansi-magenta', '#cd00cd'),
        cyan: resolveColor('--terminal-ansi-cyan', '#00cdcd'),
        white: resolveColor('--terminal-ansi-white', '#e5e5e5'),
        brightBlack: resolveColor('--terminal-ansi-bright-black', '#7f7f7f'),
        brightRed: resolveColor('--terminal-ansi-bright-red', '#ff0000'),
        brightGreen: resolveColor('--terminal-ansi-bright-green', '#00ff00'),
        brightYellow: resolveColor('--terminal-ansi-bright-yellow', '#ffff00'),
        brightBlue: resolveColor('--terminal-ansi-bright-blue', '#5c5cff'),
        brightMagenta: resolveColor('--terminal-ansi-bright-magenta', '#ff00ff'),
        brightCyan: resolveColor('--terminal-ansi-bright-cyan', '#00ffff'),
        brightWhite: resolveColor('--terminal-ansi-bright-white', '#ffffff')
    };
};

export { buildTerminalTheme };
