interface LevelBadgeProps {
  level: number;
  xp: number;
  xpToNextLevel: number;
  size?: "sm" | "md" | "lg";
}

export default function LevelBadge({ level, xp, xpToNextLevel, size = "md" }: LevelBadgeProps) {
  const progress = (xp / xpToNextLevel) * 100;

  const sizeClasses = {
    sm: { container: "w-12 h-12", text: "text-sm", ring: 20, stroke: 3 },
    md: { container: "w-20 h-20", text: "text-xl", ring: 32, stroke: 4 },
    lg: { container: "w-28 h-28", text: "text-3xl", ring: 48, stroke: 5 },
  };

  const s = sizeClasses[size];
  const circumference = 2 * Math.PI * s.ring;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  return (
    <div className={`relative ${s.container} flex items-center justify-center`}>
      <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50"
          cy="50"
          r={s.ring}
          stroke="#374151"
          strokeWidth={s.stroke}
          fill="none"
        />
        <circle
          cx="50"
          cy="50"
          r={s.ring}
          stroke="url(#levelGradient)"
          strokeWidth={s.stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          className="transition-all duration-700 ease-out"
        />
        <defs>
          <linearGradient id="levelGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#6366f1" />
          </linearGradient>
        </defs>
      </svg>
      <span className={`${s.text} font-bold text-white`}>{level}</span>
    </div>
  );
}
