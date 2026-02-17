import Navbar from "@/components/Navbar";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950">
      <Navbar />
      <main className="md:ml-64 pb-20 md:pb-0">{children}</main>
    </div>
  );
}
