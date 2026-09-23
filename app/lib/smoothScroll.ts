let activeFrame = 0;

function easeOutCubic(progress: number) {
  return 1 - Math.pow(1 - progress, 3);
}

function anchorOffset() {
  const value = window.getComputedStyle(document.documentElement).scrollPaddingTop;
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function smoothScrollToElement(element: HTMLElement, duration = 420) {
  if (activeFrame) window.cancelAnimationFrame(activeFrame);

  const start = window.scrollY;
  const destination = Math.max(0, start + element.getBoundingClientRect().top - anchorOffset());
  const distance = destination - start;

  if (Math.abs(distance) < 1) {
    window.scrollTo(0, destination);
    return;
  }

  const startedAt = performance.now();

  const step = (now: number) => {
    const progress = Math.min(1, (now - startedAt) / duration);
    window.scrollTo(0, start + distance * easeOutCubic(progress));

    if (progress < 1) activeFrame = window.requestAnimationFrame(step);
    else activeFrame = 0;
  };

  activeFrame = window.requestAnimationFrame(step);
}
