"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Scale,
  Dumbbell,
  Percent,
  Flame,
  TrendingUp,
  PlusCircle,
  Calendar,
  Trophy,
  ChevronRight,
} from "lucide-react";
import StatCard from "@/components/StatCard";
import LevelBadge from "@/components/LevelBadge";
import ProgressChart from "@/components/ProgressChart";
import { getEntries, getProfile, getAchievements } from "@/lib/store";
import { LogEntry, UserProfile, Achievement } from "@/lib/types";

export default function DashboardPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [achievements, setAchievements] = useState<Achievement[]>([]);

  useEffect(() => {
    setEntries(getEntries());
    setProfile(getProfile());
    setAchievements(getAchievements());
  }, []);

  if (!profile) return null;

  const latestEntry = entries[0];
  const previousEntry = entries[1];

  const weightTrend =
    latestEntry?.bodyWeight && previousEntry?.bodyWeight
      ? latestEntry.bodyWeight - previousEntry.bodyWeight
      : null;

  const bfTrend =
    latestEntry?.bodyFatPercentage && previousEntry?.bodyFatPercentage
      ? latestEntry.bodyFatPercentage - previousEntry.bodyFatPercentage
      : null;

  // Build weight chart data
  const weightData = [...entries]
    .filter((e) => e.bodyWeight)
    .reverse()
    .slice(-12)
    .map((e) => ({
      label: new Date(e.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      value: e.bodyWeight!,
    }));

  // Build recent lifts
  const recentLifts = entries
    .slice(0, 5)
    .flatMap((e) =>
      e.lifts.map((l) => ({
        ...l,
        entryDate: e.date,
      }))
    )
    .slice(0, 8);

  const unlockedAchievements = achievements.filter((a) => a.unlockedAt);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div className="flex items-center gap-4">
          <LevelBadge
            level={profile.level}
            xp={profile.xp}
            xpToNextLevel={profile.xpToNextLevel}
          />
          <div>
            <h1 className="text-2xl font-bold text-white">Welcome back, {profile.name}</h1>
            <p className="text-gray-400 text-sm">
              Level {profile.level} &middot; {profile.xp}/{profile.xpToNextLevel} XP
              {profile.streak > 0 && (
                <span className="ml-2 text-amber-400">
                  <Flame className="w-3.5 h-3.5 inline" /> {profile.streak} day streak
                </span>
              )}
            </p>
          </div>
        </div>
        <Link
          href="/log"
          className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-5 py-3 rounded-xl font-medium transition"
        >
          <PlusCircle className="w-5 h-5" />
          Log Workout
        </Link>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Current Weight"
          value={latestEntry?.bodyWeight ? `${latestEntry.bodyWeight} lbs` : "—"}
          icon={Scale}
          color="blue"
          trend={weightTrend ? (weightTrend > 0 ? "up" : "down") : undefined}
          trendValue={weightTrend ? `${Math.abs(weightTrend).toFixed(1)} lbs` : undefined}
        />
        <StatCard
          label="Body Fat"
          value={latestEntry?.bodyFatPercentage ? `${latestEntry.bodyFatPercentage}%` : "—"}
          icon={Percent}
          color="emerald"
          trend={bfTrend ? (bfTrend > 0 ? "up" : "down") : undefined}
          trendValue={bfTrend ? `${Math.abs(bfTrend).toFixed(1)}%` : undefined}
        />
        <StatCard
          label="Total Workouts"
          value={profile.totalWorkouts}
          icon={Dumbbell}
          color="violet"
        />
        <StatCard
          label="Day Streak"
          value={profile.streak}
          subtitle={`Best: ${profile.longestStreak}`}
          icon={Flame}
          color="amber"
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Weight chart */}
        <div className="lg:col-span-2">
          {weightData.length > 1 ? (
            <ProgressChart
              data={weightData}
              title="Weight History"
              unit="lbs"
              color="#3b82f6"
              showArea
            />
          ) : (
            <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-8 text-center">
              <Scale className="w-10 h-10 text-gray-600 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-gray-300 mb-2">No Weight Data Yet</h3>
              <p className="text-sm text-gray-500 mb-4">
                Log your first workout to see your weight history chart.
              </p>
              <Link
                href="/log"
                className="text-sm text-violet-400 hover:text-violet-300 font-medium"
              >
                Log your first entry &rarr;
              </Link>
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-300">Recent Activity</h3>
            <Link href="/log" className="text-xs text-violet-400 hover:text-violet-300">
              View All
            </Link>
          </div>

          {recentLifts.length > 0 ? (
            <div className="space-y-3">
              {recentLifts.map((lift, i) => (
                <div
                  key={`${lift.id}-${i}`}
                  className="flex items-center justify-between py-2 border-b border-gray-700/50 last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium text-white">{lift.exercise}</p>
                    <p className="text-xs text-gray-500">
                      {lift.sets}x{lift.reps} @ {lift.weight} lbs
                    </p>
                  </div>
                  <span className="text-xs text-gray-500">
                    {new Date(lift.entryDate).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Dumbbell className="w-8 h-8 text-gray-600 mx-auto mb-2" />
              <p className="text-sm text-gray-500">No lifts logged yet</p>
            </div>
          )}
        </div>
      </div>

      {/* Quick links */}
      <div className="grid md:grid-cols-3 gap-4 mt-6">
        <Link
          href="/predictions"
          className="flex items-center justify-between bg-gray-800/30 border border-gray-700/50 rounded-xl p-4 hover:border-violet-500/30 transition group"
        >
          <div className="flex items-center gap-3">
            <TrendingUp className="w-5 h-5 text-violet-400" />
            <div>
              <p className="text-sm font-medium text-white">AI Predictions</p>
              <p className="text-xs text-gray-500">View your projected gains</p>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-violet-400 transition" />
        </Link>

        <Link
          href="/achievements"
          className="flex items-center justify-between bg-gray-800/30 border border-gray-700/50 rounded-xl p-4 hover:border-violet-500/30 transition group"
        >
          <div className="flex items-center gap-3">
            <Trophy className="w-5 h-5 text-amber-400" />
            <div>
              <p className="text-sm font-medium text-white">Achievements</p>
              <p className="text-xs text-gray-500">
                {unlockedAchievements.length}/{achievements.length} unlocked
              </p>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-violet-400 transition" />
        </Link>

        <Link
          href="/settings"
          className="flex items-center justify-between bg-gray-800/30 border border-gray-700/50 rounded-xl p-4 hover:border-violet-500/30 transition group"
        >
          <div className="flex items-center gap-3">
            <Calendar className="w-5 h-5 text-emerald-400" />
            <div>
              <p className="text-sm font-medium text-white">
                Member since{" "}
                {new Date(profile.memberSince).toLocaleDateString("en-US", {
                  month: "short",
                  year: "numeric",
                })}
              </p>
              <p className="text-xs text-gray-500">{profile.subscription} plan</p>
            </div>
          </div>
          <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-violet-400 transition" />
        </Link>
      </div>
    </div>
  );
}
