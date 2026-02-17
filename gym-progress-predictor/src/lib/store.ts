"use client";

import { LogEntry, UserProfile, Achievement, Prediction } from "./types";

const STORAGE_KEYS = {
  entries: "gpp_entries",
  profile: "gpp_profile",
  achievements: "gpp_achievements",
} as const;

function getFromStorage<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : fallback;
  } catch {
    return fallback;
  }
}

function setToStorage<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(key, JSON.stringify(value));
}

const DEFAULT_PROFILE: UserProfile = {
  name: "Athlete",
  level: 1,
  xp: 0,
  xpToNextLevel: 100,
  streak: 0,
  longestStreak: 0,
  totalWorkouts: 0,
  memberSince: new Date().toISOString(),
  subscription: "free",
  goalBodyFat: 12,
  goalWeight: 180,
};

const ALL_ACHIEVEMENTS: Achievement[] = [
  {
    id: "first-log",
    name: "First Step",
    description: "Log your first workout",
    icon: "🏋️",
    category: "milestone",
    requirement: "Log 1 workout",
    progress: 0,
  },
  {
    id: "week-streak",
    name: "Week Warrior",
    description: "Maintain a 7-day logging streak",
    icon: "🔥",
    category: "consistency",
    requirement: "7-day streak",
    progress: 0,
  },
  {
    id: "month-streak",
    name: "Iron Discipline",
    description: "Maintain a 30-day logging streak",
    icon: "💎",
    category: "consistency",
    requirement: "30-day streak",
    progress: 0,
  },
  {
    id: "ten-workouts",
    name: "Getting Serious",
    description: "Complete 10 workout logs",
    icon: "💪",
    category: "milestone",
    requirement: "Log 10 workouts",
    progress: 0,
  },
  {
    id: "fifty-workouts",
    name: "Dedicated",
    description: "Complete 50 workout logs",
    icon: "🏆",
    category: "milestone",
    requirement: "Log 50 workouts",
    progress: 0,
  },
  {
    id: "body-fat-drop",
    name: "Lean Machine",
    description: "Reduce body fat by 2%",
    icon: "📉",
    category: "body",
    requirement: "Lose 2% body fat",
    progress: 0,
  },
  {
    id: "bench-plate",
    name: "Plate Club",
    description: "Bench press 135 lbs (1 plate each side)",
    icon: "🥇",
    category: "strength",
    requirement: "Bench 135 lbs",
    progress: 0,
  },
  {
    id: "squat-two-plates",
    name: "Squat Monster",
    description: "Squat 225 lbs (2 plates each side)",
    icon: "🦵",
    category: "strength",
    requirement: "Squat 225 lbs",
    progress: 0,
  },
  {
    id: "deadlift-three-plates",
    name: "Deadlift King",
    description: "Deadlift 315 lbs (3 plates each side)",
    icon: "👑",
    category: "strength",
    requirement: "Deadlift 315 lbs",
    progress: 0,
  },
  {
    id: "photo-logger",
    name: "Picture Perfect",
    description: "Upload 5 progress photos",
    icon: "📸",
    category: "milestone",
    requirement: "Upload 5 photos",
    progress: 0,
  },
];

export function getEntries(): LogEntry[] {
  return getFromStorage<LogEntry[]>(STORAGE_KEYS.entries, []);
}

export function addEntry(entry: LogEntry): LogEntry[] {
  const entries = getEntries();
  entries.push(entry);
  entries.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  setToStorage(STORAGE_KEYS.entries, entries);

  // Update profile
  const profile = getProfile();
  profile.totalWorkouts = entries.length;
  profile.xp += 25;
  if (entry.lifts.length > 0) profile.xp += entry.lifts.length * 5;
  if (entry.bodyWeight) profile.xp += 10;
  if (entry.bodyFatPercentage) profile.xp += 10;
  if (entry.photoUrl) profile.xp += 15;

  while (profile.xp >= profile.xpToNextLevel) {
    profile.xp -= profile.xpToNextLevel;
    profile.level += 1;
    profile.xpToNextLevel = Math.floor(profile.xpToNextLevel * 1.3);
  }

  // Calculate streak
  const today = new Date().toISOString().split("T")[0];
  const yesterday = new Date(Date.now() - 86400000).toISOString().split("T")[0];
  const entryDates = new Set(entries.map((e) => e.date.split("T")[0]));

  if (entryDates.has(today) || entryDates.has(yesterday)) {
    let streak = 0;
    const d = new Date();
    while (true) {
      const dateStr = d.toISOString().split("T")[0];
      if (entryDates.has(dateStr)) {
        streak++;
        d.setDate(d.getDate() - 1);
      } else {
        break;
      }
    }
    profile.streak = streak;
    profile.longestStreak = Math.max(profile.longestStreak, streak);
  } else {
    profile.streak = 1;
  }

  setToStorage(STORAGE_KEYS.profile, profile);

  // Update achievements
  updateAchievements(entries, profile);

  return entries;
}

export function deleteEntry(id: string): LogEntry[] {
  const entries = getEntries().filter((e) => e.id !== id);
  setToStorage(STORAGE_KEYS.entries, entries);
  return entries;
}

export function getProfile(): UserProfile {
  return getFromStorage<UserProfile>(STORAGE_KEYS.profile, DEFAULT_PROFILE);
}

export function updateProfile(updates: Partial<UserProfile>): UserProfile {
  const profile = { ...getProfile(), ...updates };
  setToStorage(STORAGE_KEYS.profile, profile);
  return profile;
}

export function getAchievements(): Achievement[] {
  return getFromStorage<Achievement[]>(STORAGE_KEYS.achievements, ALL_ACHIEVEMENTS);
}

function updateAchievements(entries: LogEntry[], profile: UserProfile): void {
  const achievements = getAchievements();

  for (const a of achievements) {
    switch (a.id) {
      case "first-log":
        a.progress = Math.min(100, entries.length > 0 ? 100 : 0);
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      case "week-streak":
        a.progress = Math.min(100, Math.floor((profile.streak / 7) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      case "month-streak":
        a.progress = Math.min(100, Math.floor((profile.streak / 30) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      case "ten-workouts":
        a.progress = Math.min(100, Math.floor((entries.length / 10) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      case "fifty-workouts":
        a.progress = Math.min(100, Math.floor((entries.length / 50) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      case "body-fat-drop": {
        const bfEntries = entries.filter((e) => e.bodyFatPercentage);
        if (bfEntries.length >= 2) {
          const sorted = [...bfEntries].sort(
            (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
          );
          const first = sorted[0].bodyFatPercentage!;
          const last = sorted[sorted.length - 1].bodyFatPercentage!;
          const drop = first - last;
          a.progress = Math.min(100, Math.floor((drop / 2) * 100));
          if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        }
        break;
      }
      case "bench-plate": {
        const benchMax = getMaxLift(entries, "Bench Press");
        a.progress = Math.min(100, Math.floor((benchMax / 135) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      }
      case "squat-two-plates": {
        const squatMax = getMaxLift(entries, "Squat");
        a.progress = Math.min(100, Math.floor((squatMax / 225) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      }
      case "deadlift-three-plates": {
        const dlMax = getMaxLift(entries, "Deadlift");
        a.progress = Math.min(100, Math.floor((dlMax / 315) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      }
      case "photo-logger": {
        const photos = entries.filter((e) => e.photoUrl).length;
        a.progress = Math.min(100, Math.floor((photos / 5) * 100));
        if (a.progress === 100 && !a.unlockedAt) a.unlockedAt = new Date().toISOString();
        break;
      }
    }
  }

  setToStorage(STORAGE_KEYS.achievements, achievements);
}

function getMaxLift(entries: LogEntry[], exercise: string): number {
  let max = 0;
  for (const entry of entries) {
    for (const lift of entry.lifts) {
      if (lift.exercise === exercise && lift.weight > max) {
        max = lift.weight;
      }
    }
  }
  return max;
}

export function generatePredictions(entries: LogEntry[]): Prediction | null {
  if (entries.length < 2) return null;

  const sorted = [...entries].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  const months = ["Month 1", "Month 2", "Month 3", "Month 4", "Month 5", "Month 6"];

  // Muscle gain prediction
  const weightEntries = sorted.filter((e) => e.bodyWeight && e.bodyFatPercentage);
  let muscleGain: Prediction["muscleGain"];

  if (weightEntries.length >= 2) {
    const latest = weightEntries[weightEntries.length - 1];
    const leanMass = latest.bodyWeight! * (1 - latest.bodyFatPercentage! / 100);
    const first = weightEntries[0];
    const firstLean = first.bodyWeight! * (1 - first.bodyFatPercentage! / 100);
    const daysBetween =
      (new Date(latest.date).getTime() - new Date(first.date).getTime()) / 86400000;
    const monthlyGainRate = daysBetween > 0 ? ((leanMass - firstLean) / daysBetween) * 30 : 0.5;
    const rate = Math.max(0.2, Math.min(2, monthlyGainRate));

    muscleGain = {
      currentLeanMass: Math.round(leanMass * 10) / 10,
      projectedLeanMass: months.map((_, i) => Math.round((leanMass + rate * (i + 1)) * 10) / 10),
      monthLabels: months,
      confidence: Math.min(95, 50 + entries.length * 3),
    };
  } else {
    const avgWeight = sorted.reduce((sum, e) => sum + (e.bodyWeight || 170), 0) / sorted.length;
    muscleGain = {
      currentLeanMass: Math.round(avgWeight * 0.82 * 10) / 10,
      projectedLeanMass: months.map(
        (_, i) => Math.round((avgWeight * 0.82 + 0.5 * (i + 1)) * 10) / 10
      ),
      monthLabels: months,
      confidence: 40,
    };
  }

  // Fat loss prediction
  const bfEntries = sorted.filter((e) => e.bodyFatPercentage);
  let fatLoss: Prediction["fatLoss"];

  if (bfEntries.length >= 2) {
    const latest = bfEntries[bfEntries.length - 1].bodyFatPercentage!;
    const first = bfEntries[0].bodyFatPercentage!;
    const daysBetween =
      (new Date(bfEntries[bfEntries.length - 1].date).getTime() -
        new Date(bfEntries[0].date).getTime()) /
      86400000;
    const monthlyRate = daysBetween > 0 ? ((first - latest) / daysBetween) * 30 : 0.5;
    const rate = Math.max(0.3, Math.min(2, monthlyRate));
    const goalBf = getProfile().goalBodyFat || 12;
    const weeksToGoal = rate > 0 ? Math.ceil(((latest - goalBf) / rate) * 4.3) : 52;

    fatLoss = {
      currentBodyFat: latest,
      projectedBodyFat: months.map(
        (_, i) => Math.round(Math.max(goalBf - 1, latest - rate * (i + 1)) * 10) / 10
      ),
      monthLabels: months,
      estimatedWeeksToGoal: Math.max(1, weeksToGoal),
      goalBodyFat: goalBf,
    };
  } else {
    fatLoss = {
      currentBodyFat: 20,
      projectedBodyFat: months.map((_, i) => Math.round((20 - 0.5 * (i + 1)) * 10) / 10),
      monthLabels: months,
      estimatedWeeksToGoal: 32,
      goalBodyFat: 12,
    };
  }

  // Strength predictions
  const exerciseMap = new Map<string, { date: string; weight: number }[]>();
  for (const entry of sorted) {
    for (const lift of entry.lifts) {
      if (!exerciseMap.has(lift.exercise)) exerciseMap.set(lift.exercise, []);
      exerciseMap.get(lift.exercise)!.push({ date: entry.date, weight: lift.weight });
    }
  }

  const strength: Prediction["strength"] = [];
  for (const [exercise, data] of exerciseMap) {
    if (data.length < 2) continue;
    const currentMax = Math.max(...data.map((d) => d.weight));
    const first = data[0].weight;
    const last = data[data.length - 1].weight;
    const daysBetween =
      (new Date(data[data.length - 1].date).getTime() - new Date(data[0].date).getTime()) /
      86400000;
    const monthlyRate = daysBetween > 0 ? ((last - first) / daysBetween) * 30 : 5;
    const rate = Math.max(2.5, Math.min(15, monthlyRate));

    strength.push({
      exercise,
      currentMax,
      projectedMax: months.map((_, i) => Math.round(currentMax + rate * (i + 1))),
      monthLabels: months,
    });
  }

  // Add placeholder if no strength data
  if (strength.length === 0) {
    strength.push({
      exercise: "Bench Press",
      currentMax: 135,
      projectedMax: months.map((_, i) => 135 + 5 * (i + 1)),
      monthLabels: months,
    });
  }

  return { muscleGain, fatLoss, strength };
}
