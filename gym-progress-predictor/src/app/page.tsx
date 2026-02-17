"use client";

import Link from "next/link";
import {
  Dumbbell,
  TrendingUp,
  Trophy,
  Camera,
  Zap,
  BarChart3,
  Check,
  ArrowRight,
  Flame,
  Target,
  Star,
} from "lucide-react";

const features = [
  {
    icon: Dumbbell,
    title: "Track Everything",
    description: "Log weight, lifts, body fat percentage, and progress photos in one place.",
  },
  {
    icon: TrendingUp,
    title: "AI Predictions",
    description:
      "Get personalized muscle gain trajectory, fat loss timeline, and strength projections.",
  },
  {
    icon: Trophy,
    title: "Gamified Journey",
    description:
      "Earn XP, level up, unlock achievements, and maintain streaks to stay motivated.",
  },
  {
    icon: Camera,
    title: "Photo Tracking",
    description: "Upload progress photos to visually track your body transformation over time.",
  },
  {
    icon: BarChart3,
    title: "Smart Analytics",
    description: "Beautiful charts showing your real progress and predicted future gains.",
  },
  {
    icon: Zap,
    title: "Instant Insights",
    description: "AI analyzes your data patterns and gives actionable recommendations.",
  },
];

const plans = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Get started with basic tracking",
    features: [
      "Log up to 3 workouts/week",
      "Basic progress charts",
      "Weight & lift tracking",
      "3 achievements",
    ],
    cta: "Start Free",
    popular: false,
  },
  {
    name: "Pro",
    price: "$9",
    period: "/month",
    description: "Unlock AI predictions & full gamification",
    features: [
      "Unlimited workout logs",
      "AI-powered predictions",
      "Full achievement system",
      "Progress photo uploads",
      "Strength progression analysis",
      "Body composition tracking",
      "Export your data",
    ],
    cta: "Go Pro",
    popular: true,
  },
  {
    name: "Elite",
    price: "$19",
    period: "/month",
    description: "For serious athletes who want it all",
    features: [
      "Everything in Pro",
      "Advanced AI insights",
      "Custom workout programs",
      "Priority support",
      "Detailed muscle group analysis",
      "Competition prep mode",
      "API access",
    ],
    cta: "Go Elite",
    popular: false,
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950">
      {/* Hero */}
      <header className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-violet-600/20 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-violet-900/20 via-transparent to-transparent" />

        <nav className="relative z-10 max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-xl flex items-center justify-center">
              <Dumbbell className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold text-white">GymPredict</span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/dashboard"
              className="text-sm text-gray-300 hover:text-white transition"
            >
              Dashboard
            </Link>
            <Link
              href="/dashboard"
              className="text-sm bg-violet-600 hover:bg-violet-700 text-white px-4 py-2 rounded-xl transition font-medium"
            >
              Get Started
            </Link>
          </div>
        </nav>

        <div className="relative z-10 max-w-4xl mx-auto px-6 pt-20 pb-32 text-center">
          <div className="inline-flex items-center gap-2 bg-violet-500/10 border border-violet-500/20 rounded-full px-4 py-1.5 mb-8">
            <Flame className="w-4 h-4 text-violet-400" />
            <span className="text-sm text-violet-300">AI-powered fitness predictions</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold text-white mb-6 leading-tight">
            Predict Your{" "}
            <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
              Gym Gains
            </span>{" "}
            Before They Happen
          </h1>

          <p className="text-lg md:text-xl text-gray-400 mb-10 max-w-2xl mx-auto">
            Track your workouts, body composition, and photos. Our AI predicts your muscle
            gain trajectory, fat loss timeline, and strength progression — gamifying your
            fitness journey.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-8 py-4 rounded-2xl text-lg font-semibold transition shadow-lg shadow-violet-600/25"
            >
              Start Tracking Free
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="#pricing"
              className="inline-flex items-center justify-center gap-2 bg-gray-800 hover:bg-gray-700 text-white px-8 py-4 rounded-2xl text-lg font-semibold transition border border-gray-700"
            >
              View Plans
            </Link>
          </div>

          {/* Quick stats */}
          <div className="flex flex-wrap justify-center gap-8 mt-16">
            {[
              { icon: Target, label: "Smart Predictions", value: "AI-Powered" },
              { icon: Flame, label: "Streak Tracking", value: "Stay Consistent" },
              { icon: Star, label: "Achievements", value: "10+ Badges" },
            ].map((stat) => (
              <div key={stat.label} className="flex items-center gap-3 text-left">
                <div className="w-10 h-10 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center">
                  <stat.icon className="w-5 h-5 text-violet-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">{stat.value}</p>
                  <p className="text-xs text-gray-500">{stat.label}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </header>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Everything You Need to Predict Progress
          </h2>
          <p className="text-gray-400 max-w-2xl mx-auto">
            Combine tracking, AI predictions, and gamification into one powerful tool
            that keeps you motivated and on track.
          </p>
        </div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="bg-gray-800/30 border border-gray-700/50 rounded-2xl p-6 hover:border-violet-500/30 transition group"
            >
              <div className="w-12 h-12 bg-violet-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-violet-500/20 transition">
                <feature.icon className="w-6 h-6 text-violet-400" />
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{feature.title}</h3>
              <p className="text-sm text-gray-400">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-5xl mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">How It Works</h2>
          <p className="text-gray-400">Three simple steps to unlock your fitness predictions</p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {[
            {
              step: "01",
              title: "Log Your Data",
              description:
                "Enter your weight, lifts, body fat, and progress photos after each session.",
            },
            {
              step: "02",
              title: "AI Analyzes",
              description:
                "Our algorithm analyzes your trends and builds personalized prediction models.",
            },
            {
              step: "03",
              title: "See Your Future",
              description:
                "View projected muscle gain, fat loss timeline, and strength progressions.",
            },
          ].map((item) => (
            <div key={item.step} className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/20 to-indigo-500/20 border border-violet-500/30 mb-4">
                <span className="text-2xl font-bold bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
                  {item.step}
                </span>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">{item.title}</h3>
              <p className="text-sm text-gray-400">{item.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-7xl mx-auto px-6 py-24">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Simple, Transparent Pricing
          </h2>
          <p className="text-gray-400">Start free. Upgrade when you need more power.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl p-6 border ${
                plan.popular
                  ? "bg-gradient-to-b from-violet-500/10 to-indigo-500/5 border-violet-500/40"
                  : "bg-gray-800/30 border-gray-700/50"
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-violet-600 text-white text-xs font-semibold px-3 py-1 rounded-full">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white">{plan.name}</h3>
                <div className="flex items-baseline gap-1 mt-2">
                  <span className="text-4xl font-bold text-white">{plan.price}</span>
                  <span className="text-gray-400 text-sm">{plan.period}</span>
                </div>
                <p className="text-sm text-gray-400 mt-2">{plan.description}</p>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-3 text-sm">
                    <Check className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
                    <span className="text-gray-300">{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href="/dashboard"
                className={`block text-center py-3 rounded-xl font-medium transition ${
                  plan.popular
                    ? "bg-violet-600 hover:bg-violet-700 text-white"
                    : "bg-gray-700 hover:bg-gray-600 text-white"
                }`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-4xl mx-auto px-6 py-24 text-center">
        <div className="bg-gradient-to-br from-violet-600/20 to-indigo-600/20 border border-violet-500/30 rounded-3xl p-12">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
            Ready to Predict Your Progress?
          </h2>
          <p className="text-gray-400 mb-8 max-w-xl mx-auto">
            Join thousands of athletes who use AI to visualize their fitness future and
            stay motivated on their journey.
          </p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-8 py-4 rounded-2xl text-lg font-semibold transition shadow-lg shadow-violet-600/25"
          >
            Start Your Journey
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-12">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-violet-500 to-indigo-600 rounded-lg flex items-center justify-center">
              <Dumbbell className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm text-gray-400">
              GymPredict &copy; {new Date().getFullYear()}
            </span>
          </div>
          <div className="flex gap-6 text-sm text-gray-500">
            <span className="hover:text-gray-300 cursor-pointer transition">Privacy</span>
            <span className="hover:text-gray-300 cursor-pointer transition">Terms</span>
            <span className="hover:text-gray-300 cursor-pointer transition">Support</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
