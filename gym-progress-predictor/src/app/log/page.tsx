"use client";

import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import {
  PlusCircle,
  Trash2,
  Save,
  Scale,
  Percent,
  Camera,
  Dumbbell,
  CheckCircle2,
  Clock,
  X,
} from "lucide-react";
import { COMMON_EXERCISES, LiftEntry, LogEntry } from "@/lib/types";
import { addEntry, getEntries, deleteEntry } from "@/lib/store";

export default function LogPage() {
  const [bodyWeight, setBodyWeight] = useState("");
  const [bodyFat, setBodyFat] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [lifts, setLifts] = useState<
    { exercise: string; sets: string; reps: string; weight: string }[]
  >([]);
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [saved, setSaved] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    setEntries(getEntries());
  }, []);

  const addLift = () => {
    setLifts([...lifts, { exercise: "Bench Press", sets: "3", reps: "10", weight: "" }]);
  };

  const removeLift = (index: number) => {
    setLifts(lifts.filter((_, i) => i !== index));
  };

  const updateLift = (index: number, field: string, value: string) => {
    const updated = [...lifts];
    updated[index] = { ...updated[index], [field]: value };
    setLifts(updated);
  };

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setPhotoUrl(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSave = () => {
    const liftEntries: LiftEntry[] = lifts
      .filter((l) => l.weight)
      .map((l) => ({
        id: uuidv4(),
        date: new Date().toISOString(),
        exercise: l.exercise,
        sets: parseInt(l.sets) || 3,
        reps: parseInt(l.reps) || 10,
        weight: parseFloat(l.weight) || 0,
      }));

    const entry: LogEntry = {
      id: uuidv4(),
      date: new Date().toISOString(),
      bodyWeight: bodyWeight ? parseFloat(bodyWeight) : undefined,
      bodyFatPercentage: bodyFat ? parseFloat(bodyFat) : undefined,
      photoUrl: photoUrl || undefined,
      lifts: liftEntries,
      notes: notes || undefined,
    };

    const updated = addEntry(entry);
    setEntries(updated);

    // Reset form
    setBodyWeight("");
    setBodyFat("");
    setPhotoUrl("");
    setNotes("");
    setLifts([]);

    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleDelete = (id: string) => {
    const updated = deleteEntry(id);
    setEntries(updated);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Log Workout</h1>
          <p className="text-gray-400 text-sm mt-1">
            Track your body metrics and lifts for today
          </p>
        </div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="text-sm text-gray-400 hover:text-white transition flex items-center gap-2"
        >
          <Clock className="w-4 h-4" />
          {showHistory ? "New Entry" : "History"}
        </button>
      </div>

      {saved && (
        <div className="mb-6 flex items-center gap-2 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-4 py-3 rounded-xl text-sm">
          <CheckCircle2 className="w-4 h-4" />
          Workout logged successfully! +25 XP earned.
        </div>
      )}

      {!showHistory ? (
        <div className="space-y-6">
          {/* Body Metrics */}
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Scale className="w-5 h-5 text-blue-400" />
              Body Metrics
            </h2>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400 block mb-2">Body Weight (lbs)</label>
                <input
                  type="number"
                  value={bodyWeight}
                  onChange={(e) => setBodyWeight(e.target.value)}
                  placeholder="185"
                  step="0.1"
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 transition"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-2">
                  Body Fat % <span className="text-gray-600">(optional)</span>
                </label>
                <input
                  type="number"
                  value={bodyFat}
                  onChange={(e) => setBodyFat(e.target.value)}
                  placeholder="15"
                  step="0.1"
                  min="3"
                  max="50"
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 transition"
                />
              </div>
            </div>
          </div>

          {/* Photo Upload */}
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Camera className="w-5 h-5 text-emerald-400" />
              Progress Photo <span className="text-sm text-gray-500 font-normal">(optional)</span>
            </h2>
            {photoUrl ? (
              <div className="relative">
                <img
                  src={photoUrl}
                  alt="Progress"
                  className="w-full max-w-sm rounded-xl border border-gray-700"
                />
                <button
                  onClick={() => setPhotoUrl("")}
                  className="absolute top-2 right-2 bg-gray-900/80 p-1.5 rounded-lg hover:bg-red-600/80 transition"
                >
                  <X className="w-4 h-4 text-white" />
                </button>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-gray-700 rounded-xl cursor-pointer hover:border-violet-500/50 transition">
                <Camera className="w-8 h-8 text-gray-600 mb-2" />
                <span className="text-sm text-gray-500">Click to upload a progress photo</span>
                <span className="text-xs text-gray-600 mt-1">PNG, JPG up to 10MB</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoUpload}
                  className="hidden"
                />
              </label>
            )}
          </div>

          {/* Lifts */}
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Dumbbell className="w-5 h-5 text-violet-400" />
                Lifts
              </h2>
              <button
                onClick={addLift}
                className="text-sm text-violet-400 hover:text-violet-300 font-medium flex items-center gap-1 transition"
              >
                <PlusCircle className="w-4 h-4" />
                Add Exercise
              </button>
            </div>

            {lifts.length === 0 ? (
              <div className="text-center py-8">
                <Dumbbell className="w-10 h-10 text-gray-700 mx-auto mb-3" />
                <p className="text-gray-500 text-sm mb-3">No exercises added yet</p>
                <button
                  onClick={addLift}
                  className="text-sm text-violet-400 hover:text-violet-300 font-medium"
                >
                  + Add your first exercise
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {lifts.map((lift, index) => (
                  <div
                    key={index}
                    className="bg-gray-900/50 rounded-xl p-4 border border-gray-700/50"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <select
                        value={lift.exercise}
                        onChange={(e) => updateLift(index, "exercise", e.target.value)}
                        className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500 flex-1 mr-2"
                      >
                        {COMMON_EXERCISES.map((ex) => (
                          <option key={ex.name} value={ex.name}>
                            {ex.name}
                          </option>
                        ))}
                      </select>
                      <button
                        onClick={() => removeLift(index)}
                        className="p-2 text-gray-500 hover:text-red-400 transition"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="text-xs text-gray-500 block mb-1">Sets</label>
                        <input
                          type="number"
                          value={lift.sets}
                          onChange={(e) => updateLift(index, "sets", e.target.value)}
                          min="1"
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500 block mb-1">Reps</label>
                        <input
                          type="number"
                          value={lift.reps}
                          onChange={(e) => updateLift(index, "reps", e.target.value)}
                          min="1"
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-violet-500"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500 block mb-1">Weight (lbs)</label>
                        <input
                          type="number"
                          value={lift.weight}
                          onChange={(e) => updateLift(index, "weight", e.target.value)}
                          placeholder="135"
                          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-violet-500"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-6">
            <h2 className="text-lg font-semibold text-white mb-4">
              Notes <span className="text-sm text-gray-500 font-normal">(optional)</span>
            </h2>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="How was your workout? Any PRs? How are you feeling?"
              rows={3}
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-violet-500 transition resize-none"
            />
          </div>

          {/* Save button */}
          <button
            onClick={handleSave}
            disabled={!bodyWeight && lifts.length === 0}
            className="w-full bg-violet-600 hover:bg-violet-700 disabled:bg-gray-700 disabled:text-gray-500 text-white py-4 rounded-2xl font-semibold transition flex items-center justify-center gap-2 text-lg"
          >
            <Save className="w-5 h-5" />
            Save Workout
          </button>
        </div>
      ) : (
        /* History view */
        <div className="space-y-4">
          {entries.length === 0 ? (
            <div className="text-center py-16">
              <Clock className="w-12 h-12 text-gray-700 mx-auto mb-3" />
              <h3 className="text-lg text-gray-400 font-medium">No entries yet</h3>
              <p className="text-sm text-gray-600 mt-1">Log your first workout to see it here</p>
            </div>
          ) : (
            entries.map((entry) => (
              <div
                key={entry.id}
                className="bg-gray-800/50 border border-gray-700/50 rounded-2xl p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="text-sm font-semibold text-white">
                      {new Date(entry.date).toLocaleDateString("en-US", {
                        weekday: "long",
                        month: "long",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </p>
                    <div className="flex gap-4 mt-1">
                      {entry.bodyWeight && (
                        <span className="text-xs text-gray-400">
                          {entry.bodyWeight} lbs
                        </span>
                      )}
                      {entry.bodyFatPercentage && (
                        <span className="text-xs text-gray-400">
                          {entry.bodyFatPercentage}% BF
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(entry.id)}
                    className="p-2 text-gray-600 hover:text-red-400 transition"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                {entry.lifts.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {entry.lifts.map((lift) => (
                      <div
                        key={lift.id}
                        className="flex items-center justify-between text-sm py-1"
                      >
                        <span className="text-gray-300">{lift.exercise}</span>
                        <span className="text-gray-500">
                          {lift.sets}x{lift.reps} @ {lift.weight} lbs
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {entry.notes && (
                  <p className="text-xs text-gray-500 mt-3 italic">&ldquo;{entry.notes}&rdquo;</p>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
