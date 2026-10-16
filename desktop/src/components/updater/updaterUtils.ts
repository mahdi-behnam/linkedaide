/**
 * Formatting utilities for update progress telemetry.
 * All formatters are tuned for tabular-nums legibility without jitter.
 */

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }

  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );

  if (i === 0) {
    return `${bytes} B`;
  }

  const val = bytes / Math.pow(1024, i);
  // Single decimal place precision for KB, MB, GB
  return `${val.toFixed(1)} ${units[i]}`;
}

export function formatSpeed(bytesPerSecond: number): string {
  if (!Number.isFinite(bytesPerSecond) || bytesPerSecond <= 0) {
    return "0 KB/s";
  }

  if (bytesPerSecond < 1024) {
    return `${Math.round(bytesPerSecond)} B/s`;
  }

  if (bytesPerSecond < 1024 * 1024) {
    const kb = bytesPerSecond / 1024;
    return `${kb.toFixed(1)} KB/s`;
  }

  const mb = bytesPerSecond / (1024 * 1024);
  return `${mb.toFixed(1)} MB/s`;
}

export function formatEta(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "calculating...";
  }

  const sec = Math.round(seconds);

  if (sec < 60) {
    return `${sec}s left`;
  }

  const minutes = Math.floor(sec / 60);
  const remainingSeconds = sec % 60;

  if (minutes < 60) {
    return remainingSeconds > 0
      ? `${minutes}m ${remainingSeconds}s left`
      : `${minutes}m left`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return remainingMinutes > 0
    ? `${hours}h ${remainingMinutes}m left`
    : `${hours}h left`;
}
