import { useState, useEffect, useCallback } from "react";
import type { UpdateState } from "../types/api";

export function useAppUpdater() {
  const [state, setState] = useState<UpdateState>({
    status: "idle",
    info: null,
    progress: null,
    error: null,
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.api) {
      return;
    }

    if (window.api.updaterGetStatus) {
      window.api.updaterGetStatus().then((current) => {
        if (current) {
          setState(current);
        }
      });
    }

    if (window.api.onUpdaterEvent) {
      const unsubscribe = window.api.onUpdaterEvent((incoming) => {
        setState(incoming);
      });
      return () => {
        unsubscribe();
      };
    }
  }, []);

  const startDownload = useCallback(async () => {
    if (typeof window !== "undefined" && window.api?.updaterStartDownload) {
      return await window.api.updaterStartDownload();
    }
    return false;
  }, []);

  const cancelDownload = useCallback(async () => {
    if (typeof window !== "undefined" && window.api?.updaterCancelDownload) {
      return await window.api.updaterCancelDownload();
    }
    return false;
  }, []);

  const quitAndInstall = useCallback(async () => {
    if (typeof window !== "undefined" && window.api?.updaterQuitAndInstall) {
      return await window.api.updaterQuitAndInstall();
    }
    return false;
  }, []);

  return {
    state,
    isAvailable: state.status === "available",
    isDownloading: state.status === "downloading",
    isDownloaded: state.status === "downloaded",
    hasError: state.status === "error",
    isVisible:
      state.status === "available" ||
      state.status === "downloading" ||
      state.status === "downloaded",
    startDownload,
    cancelDownload,
    quitAndInstall,
  };
}
