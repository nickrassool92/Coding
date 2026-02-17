"use client";

import { useEffect, useState } from "react";
import { Trophy, Lock, Star } from "lucide-react";
import AchievementCard from "@/components/AchievementCard";
import LevelBadge from "@/components/LevelBadge";
import { getAchievements, getProfile } from "@/lib/store";
import { Achievement, UserProfile } from "@/lib/types";

export default function AchievementsPage() {
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [filter, setFilter] = useState<"all" | "unlocked" | "locked">("all");

  useEffect(() => {
    setAchievements(getAchievements());
    setProfile(getProfile());
  }, []);

  if (!profile) return null;

  const unlocked = achievements.filter((a) => a.unlockedAt);
  const locked = achievements.filter((a) => !a.unlockedAt);

  const filtered =
    filter === "all" ? achievements : filter === "unlocked" ? unlocked : locked;

  const categories = ["all", "consistency", "strength", "body", "milestone"] as const;

  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const displayAchievements =
    categoryFilter === "all"
      ? filtered
      : filtered.filter((a) => a.category === categoryFilter);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header with level */}
      <div className="flex flex-col md:flex-row md:items-center gap-6 mb-8">
        <div className="flex items-center gap-4">
          <LevelBadge
            level={profile.level}
            xp={profile.xp}
            xpToNextLevel={profile.xpToNextLevel}
            size="lg"
          />
          <div>
            <h1 className="text-2xl font-bold text-white">Achievements</h1>
            <p className="text-gray-400 text-sm mt-1">
              Level {profile.level} &middot; {profile.xp}/{profile.xpToNextLevel} XP to
              next level
            </p>
            <div className="flex items-center gap-4 mt-2">
              <span className="text-xs text-emerald-400 flex items-center gap-1">
                <Trophy className="w-3.5 h-3.5" />
                {unlocked.length} unlocked
              </span>
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Lock className="w-3.5 h-3.5" />
                {locked.length} locked
              </span>
            </div>
          </div>
        </div>

        {/* XP Progress bar */}
        <div className="flex-1 max-w-md">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-400">Level {profile.level}</span>
            <span className="text-gray-400">Level {profile.level + 1}</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-3">
            <div
              className="h-3 rounded-full bg-gradient-to-r from-violet-500 to-indigo-500 transition-all duration-700"
              style={{
                width: `${(profile.xp / profile.xpToNextLevel) * 100}%`,
              }}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1 text-center">
            {profile.xpToNextLevel - profile.xp} XP needed for next level
          </p>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-white">{profile.totalWorkouts}</p>
          <p className="text-xs text-gray-400">Total Workouts</p>
        </div>
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-amber-400">{profile.streak}</p>
          <p className="text-xs text-gray-400">Current Streak</p>
        </div>
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-violet-400">{profile.longestStreak}</p>
          <p className="text-xs text-gray-400">Longest Streak</p>
        </div>
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4 text-center">
          <p className="text-2xl font-bold text-emerald-400">
            {Math.round((unlocked.length / achievements.length) * 100)}%
          </p>
          <p className="text-xs text-gray-400">Completion</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="flex gap-2">
          {(["all", "unlocked", "locked"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                filter === f
                  ? "bg-violet-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
              {f === "unlocked" && ` (${unlocked.length})`}
              {f === "locked" && ` (${locked.length})`}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {categories.map((c) => (
            <button
              key={c}
              onClick={() => setCategoryFilter(c)}
              className={`px-3 py-2 rounded-lg text-xs font-medium transition ${
                categoryFilter === c
                  ? "bg-gray-700 text-white"
                  : "bg-gray-800/50 text-gray-500 hover:text-gray-300"
              }`}
            >
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Achievement grid */}
      {displayAchievements.length > 0 ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {displayAchievements.map((achievement) => (
            <AchievementCard key={achievement.id} achievement={achievement} />
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <Star className="w-12 h-12 text-gray-700 mx-auto mb-3" />
          <p className="text-gray-400">No achievements match this filter</p>
        </div>
      )}
    </div>
  );
}
