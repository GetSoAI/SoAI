/* SoAI - Shared page outlet exit animation [frontend/assets/ts/core/pageoutlet/exitAnimation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type PageAnimationType = 'fade' | 'slide' | 'scale' | 'zoom' | 'lateral';

interface ExitAnimationStartState {
    opacity: string;
    transform: string;
}

const readCssNumber = (style: CSSStyleDeclaration, property: string): number => {
    const value = Number.parseFloat(style.getPropertyValue(property).trim());
    if (!Number.isFinite(value)) {
        throw new Error(`Page exit animation requires numeric CSS token ${property}`);
    }
    return value;
};

const readCssDurationMs = (style: CSSStyleDeclaration, property: string): number => {
    const value = style.getPropertyValue(property).trim().split(',')[0]?.trim() ?? '';
    if (value.endsWith('ms')) {
        const parsed = Number.parseFloat(value.slice(0, -2));
        if (Number.isFinite(parsed)) {
            return parsed;
        }
    }
    if (value.endsWith('s')) {
        const parsed = Number.parseFloat(value.slice(0, -1));
        if (Number.isFinite(parsed)) {
            return parsed * 1000;
        }
    }
    throw new Error(`Page exit animation requires duration CSS token ${property}`);
};

const resolveExitAnimationType = (section: Element): PageAnimationType => {
    const value = section.ownerDocument.documentElement.getAttribute('data-page-animation');
    if (value === 'fade' || value === 'slide' || value === 'scale' || value === 'zoom' || value === 'lateral') {
        return value;
    }
    throw new Error('Page exit animation requires a valid data-page-animation value');
};

const resolveTargetTransform = (animationType: PageAnimationType): string => {
    if (animationType === 'scale') {
        return 'scale(0.98)';
    }
    if (animationType === 'zoom') {
        return 'scale(0.96)';
    }
    if (animationType === 'lateral') {
        return 'translateX(-16px)';
    }
    if (animationType === 'fade') {
        return 'none';
    }
    return 'translateY(-8px)';
};

const buildExitKeyframes = (startState: ExitAnimationStartState, animationType: PageAnimationType): Keyframe[] => {
    return [
        {
            opacity: startState.opacity,
            transform: startState.transform
        },
        {
            opacity: '0',
            transform: resolveTargetTransform(animationType)
        }
    ];
};

const captureExitAnimationStartState = (section: Element): ExitAnimationStartState => {
    const style = getComputedStyle(section);
    return {
        opacity: style.opacity || '1',
        transform: style.transform && style.transform !== 'none' ? style.transform : 'none'
    };
};

const startPageExitAnimation = (section: Element, startState: ExitAnimationStartState): Animation => {
    const style = getComputedStyle(section);
    const animationType = resolveExitAnimationType(section);
    const duration = readCssDurationMs(style, '--effect-page-exit-duration');
    const factor = animationType === 'scale' ? readCssNumber(style, '--effect-scale-duration-factor') : 1;
    const easing = style.getPropertyValue('--ease-in').trim();
    if (!easing) {
        throw new Error('Page exit animation requires CSS token --ease-in');
    }
    return section.animate(buildExitKeyframes(startState, animationType), {
        duration: duration * factor,
        easing,
        fill: 'forwards'
    });
};

export { startPageExitAnimation, captureExitAnimationStartState };
