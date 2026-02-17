import { Achievement } from "@/lib/types";
import { Lock, CheckCircle2 } from "lucide-react";

interface AchievementCardProps {
  achievement: Achievement;
}

export default function AchievementCard({ achievement }: AchievementCardProps) {
  const isUnlocked = !!achievement.unlockedAt;

  return (
    <div
      className={`relative border rounded-2xl p-5 transition-all ${
        isUnlocked
          ? "bg-gradient-to-br from-violet-500/10 to-indigo-500/10 border-violet-500/30"
          : "bg-gray-800/30 border-gray-700/50"
      }`}
    >
      {isUnlocked && (
        <div className="absolute top-3 right-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
        </div>
      )}
      <div className="text-3xl mb-3">{isUnlocked ? achievement.icon : "🔒"}</div>
      <h3
        className={`font-semibold mb-1 ${isUnlocked ? "text-white" : "text-gray-500"}`}
      >
        {achievement.name}
      </h3>
      <p className="text-xs text-gray-400 mb-3">{achievement.description}</p>

      {/* Progress bar */}
      <div className="relative">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-500">{achievement.requirement}</span>
          <span className={isUnlocked ? "text-violet-400" : "text-gray-500"}>
            {achievement.progress}%
          </span>
        </div>
        <div className="w-full bg-gray-700/50 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              isUnlocked
                ? "bg-gradient-to-r from-violet-500 to-indigo-500"
                : "bg-gray-600"
            }`}
            style={{ width: `${achievement.progress}%` }}
          />
        </div>
      </div>

      {isUnlocked && achievement.unlockedAt && (
        <p className="text-xs text-gray-500 mt-2">
          Unlocked {new Date(achievement.unlockedAt).toLocaleDateString()}
        </p>
      )}
    </div>
  );
}
