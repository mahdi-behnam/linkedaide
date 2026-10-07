export interface ToastNotification {
  id: string;
  message: string;
  type?: "info" | "success" | "warn" | "error";
  durationMs?: number;
}
