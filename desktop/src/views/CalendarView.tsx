import React, { useState, useMemo, useCallback } from "react";
import { useApp } from "../context/AppContext";
import { ScheduledPost, NavigationTarget } from "../types";
import { useDeepNavigation } from "../hooks/useDeepNavigation";
import {
  CalendarViewMode,
  StatusFilter,
  CalendarViewProps,
} from "../components/calendar/types";
import { CalendarHeader } from "../components/calendar/CalendarHeader";
import { CalendarWeekGrid } from "../components/calendar/CalendarWeekGrid";
import { CalendarMonthGrid } from "../components/calendar/CalendarMonthGrid";
import { ScoutScheduleCard } from "../components/calendar/ScoutScheduleCard";
import { SafeguardsCard } from "../components/calendar/SafeguardsCard";
import { PostDetailModal } from "../components/calendar/PostDetailModal";

export const CalendarView: React.FC<CalendarViewProps> = ({
  initialPosts,
  initialCommentWindows,
}) => {
  const {
    scheduledPosts: contextPosts,
    commentWindows: contextCommentWindows,
    setCurrentTab,
    setActivePostForEditing,
  } = useApp();

  const scheduledPosts = initialPosts ?? contextPosts;
  const commentWindows = initialCommentWindows ?? contextCommentWindows;

  const [viewMode, setViewMode] = useState<CalendarViewMode>("week");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [selectedPost, setSelectedPost] = useState<ScheduledPost | null>(null);

  useDeepNavigation(
    "calendar",
    useCallback(
      (target: NavigationTarget) => {
        if (target.itemId) {
          const cleanId = target.itemId.replace(/^post-/, "");
          const matched = scheduledPosts.find(
            (p) => p.id === cleanId || p.id === target.itemId
          );
          if (matched) {
            setSelectedPost(matched);
          }
        }
      },
      [scheduledPosts]
    )
  );

  // Reference base date initialized to current date
  const [currentDate, setCurrentDate] = useState<Date>(() => new Date());

  // Navigate calendar
  const handlePrev = () => {
    setCurrentDate((prev) => {
      const next = new Date(prev);
      if (viewMode === "week") {
        next.setDate(next.getDate() - 7);
      } else {
        next.setMonth(next.getMonth() - 1);
      }
      return next;
    });
  };

  const handleNext = () => {
    setCurrentDate((prev) => {
      const next = new Date(prev);
      if (viewMode === "week") {
        next.setDate(next.getDate() + 7);
      } else {
        next.setMonth(next.getMonth() + 1);
      }
      return next;
    });
  };

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  // Generate 7-day week array starting on Monday of current week
  const weekDays = useMemo(() => {
    const days: Date[] = [];
    const curr = new Date(currentDate);
    const day = curr.getDay(); // 0 is Sun, 1 is Mon
    const diff = curr.getDate() - day + (day === 0 ? -6 : 1); // adjust to Monday
    const monday = new Date(curr.setDate(diff));

    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      days.push(d);
    }
    return days;
  }, [currentDate]);

  // Formatted range label
  const rangeLabel = useMemo(() => {
    if (viewMode === "week") {
      const start = weekDays[0];
      const end = weekDays[6];
      const monthNames = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
      ];
      return `${monthNames[start.getMonth()]} ${start.getDate()} - ${
        monthNames[end.getMonth()]
      } ${end.getDate()}, ${end.getFullYear()}`;
    } else {
      const monthNames = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
      ];
      return `${monthNames[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
    }
  }, [viewMode, weekDays, currentDate]);

  // Filter posts
  const filteredPosts = useMemo(() => {
    if (statusFilter === "all") return scheduledPosts;
    return scheduledPosts.filter((p) => p.status === statusFilter);
  }, [scheduledPosts, statusFilter]);

  // Switch to composer for new post
  const handleNewPost = () => {
    setActivePostForEditing(null);
    setCurrentTab("composer");
  };

  // Edit post in composer
  const handleEditInComposer = (post: ScheduledPost) => {
    setActivePostForEditing(post);
    setSelectedPost(null);
    setCurrentTab("composer");
  };

  return (
    <div className="flex flex-col gap-5 max-w-[1540px] mx-auto w-full">
      {/* Calendar Header with Stepper, View Switcher & Filters */}
      <CalendarHeader
        viewMode={viewMode}
        setViewMode={setViewMode}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        rangeLabel={rangeLabel}
        onPrev={handlePrev}
        onNext={handleNext}
        onToday={handleToday}
        onNewPost={handleNewPost}
      />

      {/* Week Grid View */}
      {viewMode === "week" && (
        <CalendarWeekGrid
          weekDays={weekDays}
          filteredPosts={filteredPosts}
          commentWindows={commentWindows}
          onSelectPost={(post) => setSelectedPost(post)}
          onNewPost={handleNewPost}
        />
      )}

      {/* Month Grid View */}
      {viewMode === "month" && (
        <CalendarMonthGrid
          currentDate={currentDate}
          filteredPosts={filteredPosts}
          onSelectPost={(post) => setSelectedPost(post)}
        />
      )}

      {/* Bottom Section: Automated Comment Scout Schedule & Safeguards */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 mt-0.5">
        {/* Left Column (7 cols): Automated Comment Scout Schedule */}
        <div id="scout-schedule" className="lg:col-span-7">
          <ScoutScheduleCard commentWindows={commentWindows} />
        </div>

        {/* Right Column (5 cols): Schedule Safeguards & Invariants */}
        <div className="lg:col-span-5">
          <SafeguardsCard />
        </div>
      </div>

      {/* Post Detail Modal */}
      {selectedPost && (
        <PostDetailModal
          post={selectedPost}
          onClose={() => setSelectedPost(null)}
          onEditInComposer={handleEditInComposer}
        />
      )}
    </div>
  );
};
