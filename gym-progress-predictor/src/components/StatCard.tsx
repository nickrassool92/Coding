import { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  trendValue?: string;
  color?: "violet" | "emerald" | "amber" | "rose" | "blue";
}

const colorMap = {
  violet: {
    bg: "bg-violet-500/10",
    border: "border-violet-500/20",
    icon: "text-violet-400",
    trend: "text-violet-400",
  },
  emerald: {
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/20",
    icon: "text-emerald-400",
    trend: "text-emerald-400",
  },
  amber: {
    bg: "bg-amber-500/10",
    border: "border-amber-500/20",
    icon: "text-amber-400",
    trend: "text-amber-400",
  },
  rose: {
    bg: "bg-rose-500/10",
    border: "border-rose-500/20",
    icon: "text-rose-400",
    trend: "text-rose-400",
  },
  blue: {
    bg: "bg-blue-500/10",
    border: "border-blue-500/20",
    icon: "text-blue-400",
    trend: "text-blue-400",
  },
};

export default function StatCard({
  label,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendValue,
  color = "violet",
}: StatCardProps) {
  const colors = colorMap[color];

  return (
    <div className={`${colors.bg} border ${colors.border} rounded-2xl p-5`}>
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2 rounded-lg ${colors.bg}`}>
          <Icon className={`w-5 h-5 ${colors.icon}`} />
        </div>
        {trend && trendValue && (
          <span
            className={`text-xs font-medium px-2 py-1 rounded-full ${
              trend === "up"
                ? "bg-emerald-500/10 text-emerald-400"
                : trend === "down"
                ? "bg-rose-500/10 text-rose-400"
                : "bg-gray-500/10 text-gray-400"
            }`}
          >
            {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"} {trendValue}
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-sm text-gray-400 mt-1">{label}</p>
      {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
    </div>
  );
}
