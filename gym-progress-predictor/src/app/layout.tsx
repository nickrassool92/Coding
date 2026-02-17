import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GymPredict - AI-Powered Gym Progress Predictor",
  description:
    "Track your workouts, body composition, and let AI predict your fitness journey. Gamified progress tracking with smart predictions.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white antialiased">{children}</body>
    </html>
  );
}
