import { useState } from "react";

export default function App() {
  const [active, setActive] = useState<number | null>(null);

  const setMode = async (mode: number) => {
    setActive(mode);
    await fetch("/api/set-led-mode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode })
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-800 text-white flex flex-col items-center justify-center p-6">
      <h1 className="text-3xl font-bold mb-8">Sterowanie LED</h1>
      <div className="flex gap-4">
        {[1, 2, 3].map((n) => (
          <button
            key={n}
            onClick={() => setMode(n)}
            className={`px-6 py-3 rounded-2xl shadow-md transition-all text-lg font-semibold ${
              active === n ? "bg-pink-500" : "bg-gray-700 hover:bg-gray-600"
            }`}
          >
            Tryb {n}
          </button>
        ))}
      </div>
    </div>
  );
}
