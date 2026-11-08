import { HealthBadge } from "../components/HealthBadge";

export function Home() {
  return (
    <main className="mx-auto max-w-3xl p-4">
      <h1 className="text-2xl font-semibold">AI PC Configuration</h1>
      <p className="mt-2 text-sm opacity-70">Подбор сборок ПК по текстовому описанию.</p>
      <p className="mt-4 text-sm">
        <HealthBadge />
      </p>
    </main>
  );
}
