// Control UI component implements the sidebar width resizer element.
import { LitElement, css, nothing } from "lit";
import { property } from "lit/decorators.js";
import { NAV_WIDTH_DEFAULT, NAV_WIDTH_MAX, NAV_WIDTH_MIN } from "../storage.ts";

/**
 * An accessible draggable divider for the left navigation sidebar.
 * Dispatches "resize" events with { navWidth: number } detail.
 */
export class SidebarResizer extends LitElement {
  @property({ type: Number }) navWidth = NAV_WIDTH_DEFAULT;
  @property({ type: Number }) minWidth = NAV_WIDTH_MIN;
  @property({ type: Number }) maxWidth = NAV_WIDTH_MAX;
  @property({ type: Number }) defaultWidth = NAV_WIDTH_DEFAULT;
  @property({ type: String }) label = "Resize sidebar";

  private isDragging = false;
  private startX = 0;
  private startWidth = 0;
  private activePointerId: number | null = null;

  static override styles = css`
    :host {
      width: 4px;
      cursor: col-resize;
      background: var(--border, #333);
      transition: background 150ms ease-out;
      flex-shrink: 0;
      position: relative;
      touch-action: none;
      user-select: none;
    }
    :host::before {
      content: "";
      position: absolute;
      top: 0;
      left: -4px;
      right: -4px;
      bottom: 0;
    }
    :host(:hover) {
      background: var(--accent, #007bff);
    }
    :host(.dragging) {
      background: var(--accent, #007bff);
    }
    :host(:focus-visible) {
      outline: 2px solid var(--accent, #007bff);
      outline-offset: 2px;
      background: var(--accent, #007bff);
    }
  `;

  override render() {
    return nothing;
  }

  override connectedCallback() {
    super.connectedCallback();
    this.classList.add("sidebar-resizer");
    this.setStaticAccessibilityAttributes();
    this.addEventListener("pointerdown", this.handlePointerDown);
    this.addEventListener("keydown", this.handleKeyDown);
    this.addEventListener("dblclick", this.handleDoubleClick);
  }

  override disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventListener("pointerdown", this.handlePointerDown);
    this.removeEventListener("keydown", this.handleKeyDown);
    this.removeEventListener("dblclick", this.handleDoubleClick);
    this.stopDragging();
  }

  protected override updated() {
    this.setAttribute("aria-valuemin", String(this.minWidth));
    this.setAttribute("aria-valuemax", String(this.maxWidth));
    this.setAttribute("aria-valuenow", String(this.clampWidth(this.navWidth)));
    if (this.label) {
      this.setAttribute("aria-label", this.label);
    } else {
      this.removeAttribute("aria-label");
    }
  }

  private handlePointerDown = (e: PointerEvent) => {
    if (e.button !== 0) {
      return;
    }
    this.isDragging = true;
    this.startX = e.clientX;
    this.startWidth = this.navWidth;
    this.classList.add("dragging");
    this.focus();
    this.capturePointer(e.pointerId);

    document.addEventListener("pointermove", this.handlePointerMove);
    document.addEventListener("pointerup", this.handlePointerUp);
    document.addEventListener("pointercancel", this.handlePointerUp);

    e.preventDefault();
  };

  private handlePointerMove = (e: PointerEvent) => {
    if (!this.isDragging) {
      return;
    }

    const deltaX = e.clientX - this.startX;
    this.emitResize(this.startWidth + deltaX);
  };

  private handlePointerUp = () => {
    this.stopDragging();
  };

  private handleKeyDown = (e: KeyboardEvent) => {
    const step = e.shiftKey ? 20 : 10;
    let nextWidth: number | null = null;

    if (e.key === "ArrowLeft") {
      nextWidth = this.navWidth - step;
    } else if (e.key === "ArrowRight") {
      nextWidth = this.navWidth + step;
    } else if (e.key === "Home") {
      nextWidth = this.minWidth;
    } else if (e.key === "End") {
      nextWidth = this.maxWidth;
    }

    if (nextWidth == null) {
      return;
    }

    e.preventDefault();
    this.emitResize(nextWidth);
  };

  private handleDoubleClick = () => {
    this.emitResize(this.defaultWidth);
  };

  private stopDragging() {
    if (!this.isDragging) {
      return;
    }
    this.isDragging = false;
    this.classList.remove("dragging");
    this.releaseActivePointer();

    document.removeEventListener("pointermove", this.handlePointerMove);
    document.removeEventListener("pointerup", this.handlePointerUp);
    document.removeEventListener("pointercancel", this.handlePointerUp);
  }

  private emitResize(nextWidth: number) {
    const navWidth = this.clampWidth(nextWidth);
    this.dispatchEvent(
      new CustomEvent("resize", {
        detail: { navWidth },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private clampWidth(value: number) {
    return Math.max(this.minWidth, Math.min(this.maxWidth, Math.round(value)));
  }

  private setStaticAccessibilityAttributes() {
    this.setAttribute("role", "separator");
    this.setAttribute("tabindex", "0");
    this.setAttribute("aria-orientation", "vertical");
  }

  private capturePointer(pointerId: number) {
    if (typeof this.setPointerCapture !== "function") {
      return;
    }
    this.setPointerCapture(pointerId);
    this.activePointerId = pointerId;
  }

  private releaseActivePointer() {
    const pointerId = this.activePointerId;
    this.activePointerId = null;
    if (pointerId == null || typeof this.releasePointerCapture !== "function") {
      return;
    }
    if (typeof this.hasPointerCapture === "function" && !this.hasPointerCapture(pointerId)) {
      return;
    }
    this.releasePointerCapture(pointerId);
  }
}

if (!customElements.get("sidebar-resizer")) {
  customElements.define("sidebar-resizer", SidebarResizer);
}

declare global {
  interface HTMLElementTagNameMap {
    "sidebar-resizer": SidebarResizer;
  }
}
