// Control UI module implements shell layout helpers.
const DESKTOP_SHELL_MIN_WIDTH_PX = 1101;

export function isDesktopShellLayout(): boolean {
  if (typeof window === "undefined") {
    return true;
  }
  if (typeof window.matchMedia !== "function") {
    return window.innerWidth >= DESKTOP_SHELL_MIN_WIDTH_PX;
  }
  return window.matchMedia(`(min-width: ${DESKTOP_SHELL_MIN_WIDTH_PX}px)`).matches;
}
