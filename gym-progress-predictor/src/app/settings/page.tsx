"use client";

import { useEffect, useState } from "react";
import {
  User,
  Target,
  CreditCard,
  Check,
  Save,
  Trash2,
  Download,
  AlertTriangle,
} from "lucide-react";
import { getProfile, updateProfile, getEntries } from "@/lib/store";
import { UserProfile } from "@/lib/types";

export default function SettingsPage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [name, setName] = useState("");
  const [goalWeight, setGoalWeight] = useState("");
  const [goalBodyFat, setGoalBodyFat] = useState("");
  const [saved, setSaved] = useState(false);
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  useEffect(() => {
    const p = getProfile();
    setProfile(p);
    setName(p.name);
    setGoalWeight(p.goalWeight?.toString() || "");
    setGoalBodyFat(p.goalBodyFat?.toString() || "");
  }, []);

  if (!profile) return null;

  const handleSave = () => {
    const updated = updateProfile({
      name: name || "Athlete",
      goalWeight: goalWeight ? parseFloat(goalWeight) : undefined,
      goalBodyFat: goalBodyFat ? parseFloat(goalBodyFat) : undefined,
    });
    setProfile(updated);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleExport = () => {
    const entries = getEntries();
    const data = {
      profile,
      entries,
      exportedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gympredict-export-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearData = () => {
    localStorage.clear();
    window.location.reload();
  };

  const plans = [
    {
      id: "free" as const,
      name: "Free",
      price: "$0",
      features: ["3 workouts/week", "Basic charts", "3 achievements"],
    },
    {
      id: "pro" as const,
      name: "Pro",
      price: "$9/mo",
      features: ["Unlimited logs", "AI predictions", "Full achievements", "Photo uploads"],
    },
    {
      id: "elite" as const,
      name: "Elite",
      price: "$19/mo",
      features: [
        "Everything in Pro",
        "Advanced insights",
        "Custom programs",
        "Priority support",
      ],
    },
  ];

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-2">Settings</h1>
      <p className="text-gray-400 text-sm mb-8">Manage your profile, goals, and subscription</p>

      {saved && (
        <div className="mb-6 flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-4 py-3 rounded-xl text-sm">
          <Check className="w-4 h-4" />
          Settings saved successfully!
        </div>
      )}

      <div className="space-y-6">
        {/* Profile */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <User className="w-5 h-5 text-violet-400" />
            Profile
          </h2>
          <div className="space-y-4">
            <div>
              <label className="text-sm text-gray-400 block mb-2">Display Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                className="w-full max-w-md bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 transition"
              />
            </div>
            <div className="grid sm:grid-cols-2 gap-4 max-w-md">
              <div>
                <label className="text-sm text-gray-400 block mb-2">
                  Member Since
                </label>
                <p className="text-white">
                  {new Date(profile.memberSince).toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </p>
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-2">Level</label>
                <p className="text-white">
                  Level {profile.level} ({profile.xp}/{profile.xpToNextLevel} XP)
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Goals */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-emerald-400" />
            Goals
          </h2>
          <p className="text-sm text-gray-400 mb-4">
            Set your target metrics for AI prediction calculations.
          </p>
          <div className="grid sm:grid-cols-2 gap-4 max-w-md">
            <div>
              <label className="text-sm text-gray-400 block mb-2">
                Target Weight (lbs)
              </label>
              <input
                type="number"
                value={goalWeight}
                onChange={(e) => setGoalWeight(e.target.value)}
                placeholder="180"
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 transition"
              />
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-2">
                Target Body Fat %
              </label>
              <input
                type="number"
                value={goalBodyFat}
                onChange={(e) => setGoalBodyFat(e.target.value)}
                placeholder="12"
                min="3"
                max="50"
                step="0.5"
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 transition"
              />
            </div>
          </div>
        </div>

        {/* Subscription */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-amber-400" />
            Subscription
          </h2>
          <div className="grid sm:grid-cols-3 gap-4">
            {plans.map((plan) => (
              <div
                key={plan.id}
                className={`border rounded-xl p-4 transition cursor-pointer ${
                  profile.subscription === plan.id
                    ? "border-violet-500 bg-violet-500/10"
                    : "border-gray-700 hover:border-gray-600"
                }`}
                onClick={() => {
                  const updated = updateProfile({ subscription: plan.id });
                  setProfile(updated);
                }}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-white">{plan.name}</span>
                  {profile.subscription === plan.id && (
                    <span className="text-xs bg-violet-600 text-white px-2 py-0.5 rounded-full">
                      Current
                    </span>
                  )}
                </div>
                <p className="text-xl font-bold text-white mb-3">{plan.price}</p>
                <ul className="space-y-1">
                  {plan.features.map((f) => (
                    <li key={f} className="text-xs text-gray-400 flex items-start gap-2">
                      <Check className="w-3 h-3 text-violet-400 mt-0.5 shrink-0" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Save button */}
        <button
          onClick={handleSave}
          className="bg-violet-600 hover:bg-violet-700 text-white px-6 py-3 rounded-xl font-medium transition flex items-center gap-2"
        >
          <Save className="w-4 h-4" />
          Save Settings
        </button>

        {/* Data Management */}
        <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Data Management</h2>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={handleExport}
              className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 text-white px-4 py-2.5 rounded-xl text-sm transition"
            >
              <Download className="w-4 h-4" />
              Export Data (JSON)
            </button>
            {!showClearConfirm ? (
              <button
                onClick={() => setShowClearConfirm(true)}
                className="flex items-center gap-2 bg-red-500/10 hover:bg-red-500/20 text-red-400 px-4 py-2.5 rounded-xl text-sm transition border border-red-500/20"
              >
                <Trash2 className="w-4 h-4" />
                Clear All Data
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-sm text-red-400 flex items-center gap-1">
                  <AlertTriangle className="w-4 h-4" />
                  Are you sure?
                </span>
                <button
                  onClick={handleClearData}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm transition"
                >
                  Yes, delete everything
                </button>
                <button
                  onClick={() => setShowClearConfirm(false)}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm transition"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
