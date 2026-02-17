export interface WeightEntry {
  id: string;
  date: string;
  weight: number; // lbs
  bodyFatPercentage?: number;
  photoUrl?: string;
}

export interface LiftEntry {
  id: string;
  date: string;
  exercise: string;
  sets: number;
  reps: number;
  weight: number; // lbs
}

export interface LogEntry {
  id: string;
  date: string;
  bodyWeight?: number;
  bodyFatPercentage?: number;
  photoUrl?: string;
  lifts: LiftEntry[];
  notes?: string;
}

export interface Prediction {
  muscleGain: {
    currentLeanMass: number;
    projectedLeanMass: number[];
    monthLabels: string[];
    confidence: number;
  };
  fatLoss: {
    currentBodyFat: number;
    projectedBodyFat: number[];
    monthLabels: string[];
    estimatedWeeksToGoal: number;
    goalBodyFat: number;
  };
  strength: {
    exercise: string;
    currentMax: number;
    projectedMax: number[];
    monthLabels: string[];
  }[];
}

export interface Achievement {
  id: string;
  name: string;
  description: string;
  icon: string;
  unlockedAt?: string;
  category: "consistency" | "strength" | "body" | "milestone";
  requirement: string;
  progress: number; // 0-100
}

export interface UserProfile {
  name: string;
  level: number;
  xp: number;
  xpToNextLevel: number;
  streak: number;
  longestStreak: number;
  totalWorkouts: number;
  memberSince: string;
  subscription: "free" | "pro" | "elite";
  goalBodyFat?: number;
  goalWeight?: number;
}

export type ExerciseCategory = "compound" | "isolation" | "bodyweight" | "cardio";

export interface ExerciseDefinition {
  name: string;
  category: ExerciseCategory;
  muscleGroups: string[];
}

export const COMMON_EXERCISES: ExerciseDefinition[] = [
  { name: "Bench Press", category: "compound", muscleGroups: ["chest", "triceps", "shoulders"] },
  { name: "Squat", category: "compound", muscleGroups: ["quads", "glutes", "hamstrings"] },
  { name: "Deadlift", category: "compound", muscleGroups: ["back", "glutes", "hamstrings"] },
  { name: "Overhead Press", category: "compound", muscleGroups: ["shoulders", "triceps"] },
  { name: "Barbell Row", category: "compound", muscleGroups: ["back", "biceps"] },
  { name: "Pull-Up", category: "bodyweight", muscleGroups: ["back", "biceps"] },
  { name: "Dip", category: "bodyweight", muscleGroups: ["chest", "triceps"] },
  { name: "Leg Press", category: "compound", muscleGroups: ["quads", "glutes"] },
  { name: "Romanian Deadlift", category: "compound", muscleGroups: ["hamstrings", "glutes"] },
  { name: "Lat Pulldown", category: "isolation", muscleGroups: ["back", "biceps"] },
  { name: "Bicep Curl", category: "isolation", muscleGroups: ["biceps"] },
  { name: "Tricep Extension", category: "isolation", muscleGroups: ["triceps"] },
  { name: "Lateral Raise", category: "isolation", muscleGroups: ["shoulders"] },
  { name: "Leg Curl", category: "isolation", muscleGroups: ["hamstrings"] },
  { name: "Leg Extension", category: "isolation", muscleGroups: ["quads"] },
  { name: "Cable Fly", category: "isolation", muscleGroups: ["chest"] },
  { name: "Face Pull", category: "isolation", muscleGroups: ["shoulders", "back"] },
  { name: "Calf Raise", category: "isolation", muscleGroups: ["calves"] },
];
