import { useState, useCallback } from "react";
import { ScheduledPost } from "../types";

export function useScheduledPosts(onMessage?: (msg: string) => void) {
  const [scheduledPosts, setScheduledPosts] = useState<ScheduledPost[]>(() => {
    if (typeof window !== "undefined" && window.localStorage) {
      try {
        const saved = localStorage.getItem("hitl_scheduled_posts");
        return saved ? JSON.parse(saved) : [];
      } catch {
        return [];
      }
    }
    return [];
  });
  const [activePostForEditing, setActivePostForEditing] = useState<ScheduledPost | null>(null);

  const saveScheduledPost = useCallback(
    (post: ScheduledPost) => {
      setScheduledPosts((prev) => {
        const idx = prev.findIndex((p) => p.id === post.id);
        const next = idx >= 0 ? [...prev] : [post, ...prev];
        if (idx >= 0) next[idx] = post;
        if (typeof window !== "undefined" && window.localStorage) {
          try {
            localStorage.setItem("hitl_scheduled_posts", JSON.stringify(next));
          } catch {
            // ignore
          }
        }
        return next;
      });
      onMessage?.(`Post saved successfully: "${post.headline || post.id}"`);
    },
    [onMessage]
  );

  const deleteScheduledPost = useCallback(
    (id: string) => {
      setScheduledPosts((prev) => {
        const next = prev.filter((p) => p.id !== id);
        if (typeof window !== "undefined" && window.localStorage) {
          try {
            localStorage.setItem("hitl_scheduled_posts", JSON.stringify(next));
          } catch {
            // ignore
          }
        }
        return next;
      });
      onMessage?.("Scheduled post removed");
    },
    [onMessage]
  );

  return {
    scheduledPosts,
    setScheduledPosts,
    activePostForEditing,
    setActivePostForEditing,
    saveScheduledPost,
    deleteScheduledPost,
  };
}
