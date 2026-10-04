import { useState, useCallback, useEffect } from "react";
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

  // Initial fetch from backend if available
  useEffect(() => {
    let isMounted = true;
    if (typeof window !== "undefined" && window.api?.fetchScheduledPosts) {
      window.api
        .fetchScheduledPosts()
        .then((remotePosts: ScheduledPost[]) => {
          if (isMounted && Array.isArray(remotePosts) && remotePosts.length > 0) {
            setScheduledPosts(remotePosts as ScheduledPost[]);
            try {
              localStorage.setItem("hitl_scheduled_posts", JSON.stringify(remotePosts));
            } catch {
              // ignore
            }
          }
        })
        .catch(() => {
          // ignore network failure, fallback to localStorage
        });
    }
    return () => {
      isMounted = false;
    };
  }, []);

  const saveScheduledPost = useCallback(
    async (post: ScheduledPost) => {
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

      if (typeof window !== "undefined" && window.api?.saveScheduledPost) {
        try {
          await window.api.saveScheduledPost(post as any);
        } catch {
          // fallback to local
        }
      }

      onMessage?.(`Post saved successfully: "${post.headline || post.id}"`);
    },
    [onMessage]
  );

  const deleteScheduledPost = useCallback(
    async (id: string) => {
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

      if (typeof window !== "undefined" && window.api?.deleteScheduledPost) {
        try {
          await window.api.deleteScheduledPost(id);
        } catch {
          // fallback to local
        }
      }

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
