"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  TrendingUp,
  Dumbbell,
  Target,
  Timer,
  Brain,
  ArrowRight,
  Zap,
  Activity,
} from "lucide-react";
import ProgressChart from "@/components/ProgressChart";
import { getEntries, generatePredictions } from "@/lib/store";
import { LogEntry, Prediction } from "@/lib/types";

export default function PredictionsPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [predictions, setPredictions] = useState<Prediction | null>(null);

  useEffect(() => {
    const e = getEntries();
    setEntries(e);
    setPredictions(generatePredictions(e));
  }, []);

  if (entries.length < 2) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold text-white mb-2">AI Predictions</h1>
        <p className="text-gray-400 text-sm mb-8">
          Powered by trend analysis of your workout data
        </p>

        <div className="text-center py-20">
          <div className="w-20 h-20 bg-violet-500/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
            <Brain className="w-10 h-10 text-violet-400" />
          </div>
          <h2 className="text-xl font-semibold text-white mb-3">Need More Data</h2>
          <p className="text-gray-400 max-w-md mx-auto mb-6">
            Log at least 2 workouts with body metrics so our AI can analyze your trends and
            generate personalized predictions.
          </p>
          <div className="flex items-center justify-center gap-4">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <div className={`w-3 h-3 rounded-full ${entries.length >= 1 ? "bg-violet-500" : "bg-gray-700"}`} />
              Entry 1 {entries.length >= 1 ? "done" : "needed"}
            </div>
            <div className="w-8 h-px bg-gray-700" />
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <div className={`w-3 h-3 rounded-full ${entries.length >= 2 ? "bg-violet-500" : "bg-gray-700"}`} />
              Entry 2 {entries.length >= 2 ? "done" : "needed"}
            </div>
            <div className="w-8 h-px bg-gray-700" />
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <div className="w-3 h-3 rounded-full bg-gray-700" />
              Predictions unlock
            </div>
          </div>
          <Link
            href="/log"
            className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-6 py-3 rounded-xl font-medium transition mt-8"
          >
            Log a Workout
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    );
  }

  if (!predictions) return null;

  const muscleChartData = [
    { label: "Now", value: predictions.muscleGain.currentLeanMass },
    ...predictions.muscleGain.projectedLeanMass.map((v, i) => ({
      label: predictions.muscleGain.monthLabels[i],
      value: v,
    })),
  ];

  const fatChartData = [
    { label: "Now", value: predictions.fatLoss.currentBodyFat },
    ...predictions.fatLoss.projectedBodyFat.map((v, i) => ({
      label: predictions.fatLoss.monthLabels[i],
      value: v,
    })),
  ];

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Brain className="w-7 h-7 text-violet-400" />
          AI Predictions
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Based on {entries.length} logged entries &middot;{" "}
          {predictions.muscleGain.confidence}% confidence
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid sm:grid-cols-3 gap-4 mb-8">
        <div className="bg-gradient-to-br from-blue-500/10 to-cyan-500/10 border border-blue-500/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-5 h-5 text-blue-400" />
            <span className="text-sm font-medium text-blue-300">Muscle Gain</span>
          </div>
          <p className="text-2xl font-bold text-white">
            +{(
              predictions.muscleGain.projectedLeanMass[5] -
              predictions.muscleGain.currentLeanMass
            ).toFixed(1)}{" "}
            lbs
          </p>
          <p className="text-xs text-gray-400 mt-1">Projected lean mass in 6 months</p>
        </div>

        <div className="bg-gradient-to-br from-emerald-500/10 to-green-500/10 border border-emerald-500/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-5 h-5 text-emerald-400" />
            <span className="text-sm font-medium text-emerald-300">Fat Loss Goal</span>
          </div>
          <p className="text-2xl font-bold text-white">
            {predictions.fatLoss.goalBodyFat}% BF
          </p>
          <p className="text-xs text-gray-400 mt-1">
            ~{predictions.fatLoss.estimatedWeeksToGoal} weeks to reach goal
          </p>
        </div>

        <div className="bg-gradient-to-br from-violet-500/10 to-purple-500/10 border border-violet-500/20 rounded-2xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-5 h-5 text-violet-400" />
            <span className="text-sm font-medium text-violet-300">Top Lift Growth</span>
          </div>
          <p className="text-2xl font-bold text-white">
            {predictions.strength.length > 0
              ? `+${predictions.strength[0].projectedMax[5] - predictions.strength[0].currentMax} lbs`
              : "—"}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {predictions.strength[0]?.exercise || "No data"} in 6 months
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid lg:grid-cols-2 gap-6 mb-8">
        <ProgressChart
          data={muscleChartData}
          title="Lean Muscle Mass Projection"
          unit="lbs"
          color="#3b82f6"
          showArea
        />
        <ProgressChart
          data={fatChartData}
          title="Body Fat % Projection"
          unit="%"
          color="#10b981"
          showArea
        />
      </div>

      {/* Strength Projections */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <Dumbbell className="w-5 h-5 text-violet-400" />
          Strength Projections
        </h2>
        <div className="grid lg:grid-cols-2 gap-6">
          {predictions.strength.map((s) => (
            <ProgressChart
              key={s.exercise}
              data={[
                { label: "Now", value: s.currentMax },
                ...s.projectedMax.map((v, i) => ({
                  label: s.monthLabels[i],
                  value: v,
                })),
              ]}
              title={s.exercise}
              unit="lbs"
              color="#8b5cf6"
            />
          ))}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="bg-gray-800/30 border border-gray-700/50 rounded-xl p-4 text-center">
        <p className="text-xs text-gray-500">
          Predictions are based on trend analysis of your logged data and general fitness
          models. Individual results vary based on diet, sleep, genetics, and training
          intensity. Confidence increases with more data points.
        </p>
      </div>
    </div>
  );
}
