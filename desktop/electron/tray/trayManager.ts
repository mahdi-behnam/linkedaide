/**
 * System Tray Manager for LinkedIn HITL Desktop
 *
 * Manages the Electron Tray lifecycle, status badge tooltips,
 * context menu actions, and window visibility toggling.
 */

import {
  app,
  BrowserWindow,
  Menu,
  MenuItemConstructorOptions,
  nativeImage,
  NativeImage,
  Tray,
} from "electron";
import { WorkerClient } from "../api/workerClient";

import * as fs from "fs";
import * as path from "path";

/**
 * 16x16 RGBA PNG base64 Data URLs for LinkedAide status states:
 * - Active: normal teal round icon
 * - Standby: gray round icon (paused)
 * - Attention: round icon with exclamation badge (pending reviews)
 */
export const TRAY_ACTIVE_ICON_DATA_URL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADcklEQVR4nF2TX0xWZRzHv7/nOee87wse/okzIYi/AUJbxktjAyaRzkZloHtZtVZtzaxWzTGDyBrFiAvZrLSsTdm6sdxLrFKWullRN0GmrK1sbYybZl4oDeE9L+ec5zzPrwvypu/N9+Zz+fkQ1kf/Pb9w8nhTwHiegS4ApUIISNv6O+bYPzgSJ46knplfJ5lAxASAMDxMNDJinjh6ZEQL6rccJ1cAiLSGEALxWAyWY4GY12xBH3aInKG+vj4DZlAqnZbpVMrsHT/8mZ3vPh56HixBOjSRKMh1IaXAqu8jNx4zJKR0NxYgymSnUyUVvcdv3GACgEfHRt+y3LyR0MuEjmXZXhhSe30dDj68G0SEjy5ewOziAtxEnAFW7qZiR62sjn/81HMD1DM2dndWR7+SkLYkCAbTlqJCTOx/CV//8jM0M3qS92P/pyeQDQM4tsVSSiOl5DxpNQvPD1/UJOJKhWAD8vwAm918fDk3h6Pnz2Fi5lssra4i1dKKlewawESR0iDLtjKReln4Wu0Mw5CNMeSrEG48ge1bG9FUXo5XH+qG1gbfX/0NOxrvQVlRETzfBzOLMAhYRaZLhJEuVVFEbEC3vCwGe3rQVl+PSwsLaK2pRXNFNe4q3gRBhKfbtiNQIQwzRaEibUyJ0NqADfBPJoPOxq3oaGjAe2fPIlldjZmrv+Ox5iS2VVTi8Jmv0FpTi47aetzyPACA0QYWmK8rbfJtKXmgt5cuzM9janYWdxQWYHeyBZkgwJunP8ePf/6BbRWV2PfADlxaXODIGNiE68K27YsrQUjt9Q28yXUx+sUUEo6D2i0leGdyEu9PT+PJ9g4Ub3Bx7Pw55MZiaKmsMWtKkSQxI+50Cz+BjsLl7BqEENxaV4eh3j3obGzEtaWb+GvpJprKytDf/QiSVdWwpORsqBD5SufZ9jECgNbXBkdXSR46uGtn+GxXp73seTR06hSuLC7CsiTuq6rC23192LjB5W8uX1YTcz85jlLjpw/0D1AqlZLpdJqT/QOTWSn3bI7HEahAe0Eg3JwEWVJAac15OQmTn5MrM0SIRerMK8mWvbdVpvW4GG2vv/Huih8ekLaVcKQAgSGlQMxxIC0LxOznJWIfTJVXHKLbMf0/5+7h4XuXQ71P6ehBMJdaUsJxrGs58fh3rpQn04ODV9ZJEAj8LzR+hTD9aV5BAAAAAElFTkSuQmCC";

export const TRAY_STANDBY_ICON_DATA_URL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADMklEQVR4nE2Tz0tjVxiG3++ckxvFBBOJSjJlDFGQ+gMKzU5c2FGmIkp/pFl0VjKFDLOoFEQcKDTtolUULBQHCv0DbCgUaTCItAR0aXFAdJdYhepCCGr0aO6953xdzLT12byb91k+hNfQm+WFhYVBpdRnxpj3mPkBAAghTomozMw/zc3Nvbr/JwDEzACApaWlbwB8oZRqMcbA930AgFIKQggYY26Z+Xut9Zf5fJ6JCFQoFOTBwQE3NTX9HAqFMtfX12Bm47quCAaDMMbAWgullAUgw+Ewbm5ufk2lUp8AgMhms6a5ufmrcDicqdfrLgC+u7uT/f39NDMzQ8+e5SgWi5Hv+5KI+Orqym1pafmwUql8nc1mDa2srLzdaDReMbNkZmGMofb2duRyOZTLZSQSCbS1tWF1dRXBYBDWWhZCWABWKfWOcF33eSAQcKy1EEKQ53mIRqPY3t5GsVjE+vo6otEoBgYGoLWGEIKstXAcJ+B53nNhrR01xvC/ciQSweDgILq7u5HJfIzLy0tUq1WMjo7CcRxYa0FE5Ps+E9EjwcwPjDHEzMLzPGQyGXR2dqJSqeDhwy709vYiFouhtbUVQ0ND0FqDiMQb5y3BzIKIoLVGOp1GPB5HqVRCX18fzs7OMDk5iVqthkKhgJGREcTjcbiuCyICM5MgolNm5lAoZMfGxrCzs4P9/X3s7u6io6MDJycnKBaL2Nvbw/HxMSYmJuD7vhVCMBGdCqXU79ZaSqVSrJTC1tYWEokE0uk01tbWcHRUxZMnn8Jai83NTSSTSUQiEabX/KGklC8bjcbTWq0mhBA8NTVFPT09uL29hdYaR0d/4fHj9zE9PQ2lFC4uLrjRaICIfCnlSwKAxcXFb5VSL7q6utzh4eHA+fk5bWxswHVd+L6PeDyO8fFxMDOXSiVPa+24rrs4Pz8/T4VCQQJAtVr9RSn1Qb1eh7XWOI4jhBBERPA8j33ft0QkI5EIPM/7TWv90eHh4f8x5fN5CoVC3wH4XErZ5HkejDEAACkllFKw1t4x8w/JZPJFNpu19zP+L8/l5eV3mTlnrX1kjIkTEUsp/yaiMhH9ODs7++c9h/8B73yc4o6MfEgAAAAASUVORK5CYII=";

export const TRAY_ATTENTION_ICON_DATA_URL =
  "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADgUlEQVR4nE3TS2xUVRzH8d//nHPvPGs7MzXt0LGItohtIhIrMTyltuLCykJHsEaiAapR4iPBBgjY1GB9JCpBECJVSQwEpi5Q0FVtxMRoCAsjVZ4iGkMt1jKduTN35t57zt8F0fhZf7dfwnUEZoCIn967ty0QvI4JXUzmJhKSlSX/CEs1NhGbvW//xbdujgQz/Y62zuZbF21VAAgDA0RE5vFdOwcc422S0ooTMwQTmBham2QlGr6jtXhugX1lfK5975Pp5OVTnfqHL6XK5nIil82a1bHIIWPbj/nlEqTnawMWXhCApEAsEtIgRcnqtFZeJTXtuKgLqiDCAgKAVUM7tlvxmle9UsmzpLA0mBLxGNbfdz+kEDhwYowd45Mdjp5/7bePf22MWot0qTDtUKiPVg8Nzc37/o9CkJJEQilFIMZ76/ugtYavDaQQ2Hr4E47UxIkhLt7pXv59uiZtzqXmPSem3eqzRqiQ72swMzmui5aGNKZmZrBx+AO8cuQgmutTWHJbG81cy0PBtJyM3tI5GUt1pf669JKo+n6353tsmCnQDDCjLZOBpzV6Ou7G34UCxsZPo3fJUoRtG1W3wna1pP1CwXjGrBBVbZp8zycANFUs4qnOLqxd0Ymr1/Lo6ViIu+bcimS8BolYHKs6FqJQLhNBSO37QhvTJIwBtGHkS2W0ZTLoXb4Mbx89iqZUCicvnEfvsuWYXX8jdn1xDI/esxgtjWkUXRdkANYago2ZCEDsBQFveeRhfHvmDA6e+AZfj4+jvbkZgTbYMZLDyPff4dQvF/BM9wPwjTEGxKwxIWwlRyt+QK3pWXx7JoPBwzmELAvd8+fjnc8+x0ejo3ix5yHE7TB2Hj+GloZGzEnWc0VrIuArlYzae0r50obJfEHNlMv8Qs+D1FBXi4ZEApf+nISlBKIhG28+sRZXCwU4rstTRQcc+H40XrtbHB8cPFsbsl8vaCM37hv2ZyUSXKpWsWH3HjiVCoquh+eHP4RTrSBdV8eDuSO+C8gQiTfe7+v7ibLZrMzlcmbxy1sOFSHWlIsFSGJ9QzQqoiEbSkpoNvCCwFhKyLpkEhFjRuY5pTU/t7cT/XsiEfHS/m0DFaM3kVRxYg2QgSUlbMtGKByCZC6FlXz30/7+7cxMIAL9t/N1vLJ/W7sDXhew6SLWGUtJWJZ1JRKyx6JK7R/ZvPn0//t/APgkrQVJ93TlAAAAAElFTkSuQmCC";

export const FALLBACK_TRAY_ICON_DATA_URL = TRAY_ACTIVE_ICON_DATA_URL;

export function getTrayIcon(state: "active" | "standby" | "attention" = "active"): NativeImage {
  const assetName = `tray-${state}.png`;
  const possiblePaths = [
    path.join(__dirname, "assets", assetName),
    path.join(__dirname, "../assets/icons", `round-${state}.png`),
    path.join(process.cwd(), "desktop/electron/tray/assets", assetName),
  ];
  if (typeof nativeImage.createFromPath === "function") {
    for (const p of possiblePaths) {
      if (fs.existsSync(p)) {
        return nativeImage.createFromPath(p);
      }
    }
  }
  const dataUrl =
    state === "standby"
      ? TRAY_STANDBY_ICON_DATA_URL
      : state === "attention"
      ? TRAY_ATTENTION_ICON_DATA_URL
      : TRAY_ACTIVE_ICON_DATA_URL;
  return nativeImage.createFromDataURL(dataUrl);
}

export function createFallbackTrayIcon(): NativeImage {
  return getTrayIcon("active");
}

export interface TrayManagerOptions {
  mainWindow?: BrowserWindow | null;
  workerClient: WorkerClient;
  initialPaused?: boolean;
}

export class TrayManager {
  private tray: Tray | null = null;
  private mainWindow: BrowserWindow | null = null;
  private workerClient: WorkerClient;
  private isPaused: boolean = false;
  private pendingCount: number = 0;

  constructor(
    mainWindowOrOptions?: BrowserWindow | null | TrayManagerOptions,
    workerClient?: WorkerClient,
    initialPaused: boolean = false
  ) {
    if (
      mainWindowOrOptions &&
      typeof mainWindowOrOptions === "object" &&
      "workerClient" in mainWindowOrOptions
    ) {
      this.mainWindow = mainWindowOrOptions.mainWindow ?? null;
      this.workerClient = mainWindowOrOptions.workerClient;
      this.isPaused = mainWindowOrOptions.initialPaused ?? false;
    } else {
      this.mainWindow = (mainWindowOrOptions as BrowserWindow | null) ?? null;
      this.workerClient = workerClient!;
      this.isPaused = initialPaused;
    }

    this.initTray();
  }

  /**
   * Initializes the Tray instance with the fallback icon and default context menu.
   */
  private initTray(): void {
    const icon = getTrayIcon(this.isPaused ? "standby" : "active");
    this.tray = new Tray(icon);
    this.tray.setToolTip("LinkedIn HITL Agent");
    this.updateContextMenu();

    this.tray.on("click", () => {
      this.openDashboard();
    });
  }

  /**
   * Updates the reference to the main application window.
   */
  public setMainWindow(win: BrowserWindow | null): void {
    this.mainWindow = win;
  }

  public getMainWindow(): BrowserWindow | null {
    return this.mainWindow;
  }

  public getTray(): Tray | null {
    return this.tray;
  }

  public getIsPaused(): boolean {
    return this.isPaused;
  }

  public getPendingCount(): number {
    return this.pendingCount;
  }

  /**
   * Restores, shows, and focuses the main application window.
   */
  public openDashboard(): void {
    if (this.mainWindow) {
      if (this.mainWindow.isMinimized()) {
        this.mainWindow.restore();
      }
      this.mainWindow.show();
      this.mainWindow.focus();
    }
  }

  /**
   * Constructs the MenuItem template for the tray context menu.
   */
  public getContextMenuTemplate(): MenuItemConstructorOptions[] {
    return [
      {
        label: "Open Dashboard",
        click: () => {
          this.openDashboard();
        },
      },
      {
        label: "Trigger Scout Now",
        click: async () => {
          try {
            await this.workerClient.triggerScout();
          } catch (err) {
            console.error("TrayManager: failed to trigger scout:", err);
          }
        },
      },
      {
        label: "Pause / Resume Agent",
        type: "checkbox",
        checked: this.isPaused,
        click: async () => {
          const nextState = !this.isPaused;
          try {
            await this.workerClient.togglePause(nextState);
            this.setPaused(nextState);
          } catch (err) {
            console.error("TrayManager: failed to toggle pause:", err);
          }
        },
      },
      {
        label: "Reset Circuit Breaker",
        click: async () => {
          try {
            await this.workerClient.clearIncident();
          } catch (err) {
            console.error("TrayManager: failed to reset circuit breaker:", err);
          }
        },
      },
      {
        type: "separator",
      },
      {
        label: "Quit",
        click: () => {
          app.quit();
        },
      },
    ];
  }

  /**
   * Builds and sets the context menu on the tray instance.
   */
  public updateContextMenu(): void {
    if (
      this.tray &&
      (typeof this.tray.isDestroyed !== "function" || !this.tray.isDestroyed())
    ) {
      const template = this.getContextMenuTemplate();
      const menu = Menu.buildFromTemplate(template);
      this.tray.setContextMenu(menu);
    }
  }

  /**
   * Updates the tray tooltip and macOS menu bar title with the pending count.
   */
  public updateBadge(pendingCount: number): void {
    this.pendingCount = Math.max(0, pendingCount);
    const tooltip =
      this.pendingCount > 0
        ? `LinkedIn HITL Agent (${this.pendingCount} pending)`
        : "LinkedIn HITL Agent";
    const title = this.pendingCount > 0 ? ` (${this.pendingCount})` : "";

    if (
      this.tray &&
      (typeof this.tray.isDestroyed !== "function" || !this.tray.isDestroyed())
    ) {
      this.tray.setToolTip(tooltip);
      if (typeof this.tray.setTitle === "function") {
        this.tray.setTitle(title);
      }
      this.updateTrayIcon();
    }
  }

  /**
   * Dynamically updates the tray icon image based on current state:
   * - Standby (paused)
   * - Attention (pendingCount > 0)
   * - Active (normal monitoring)
   */
  public updateTrayIcon(): void {
    if (
      !this.tray ||
      (typeof this.tray.isDestroyed === "function" && this.tray.isDestroyed())
    ) {
      return;
    }
    const state = this.isPaused
      ? "standby"
      : this.pendingCount > 0
      ? "attention"
      : "active";
    if (typeof this.tray.setImage === "function") {
      this.tray.setImage(getTrayIcon(state));
    }
  }

  /**
   * Updates the paused state and rebuilds the context menu.
   */
  public setPaused(isPaused: boolean): void {
    this.isPaused = isPaused;
    this.updateContextMenu();
    this.updateTrayIcon();
  }

  /**
   * Cleans up the tray instance on application shutdown.
   */
  public destroy(): void {
    if (this.tray) {
      if (
        typeof this.tray.isDestroyed !== "function" ||
        !this.tray.isDestroyed()
      ) {
        this.tray.destroy();
      }
      this.tray = null;
    }
  }
}
