import { useEffect, useState } from "react";

const STEPS = ["Разбираю запрос", "Подбираю комплектующие", "Проверяю совместимость"];

export function ProgressSteps({ active }: { active: boolean }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timers = [setTimeout(() => setStep(1), 900), setTimeout(() => setStep(2), 2200)];
    return () => {
      timers.forEach(clearTimeout);
      setStep(0);
    };
  }, [active]);
  if (!active) return null;
  return (
    <ol className="flex flex-wrap items-center gap-2 font-mono text-xs" aria-live="polite">
      {STEPS.map((s, i) => (
        <li
          key={s}
          className={`flex items-center gap-2 ${i <= step ? "text-accent" : "text-mute"}`}
        >
          <span>{i < step ? "✓" : i === step ? "●" : "○"}</span>
          {s}
          {i < STEPS.length - 1 && <span className="text-mute">→</span>}
        </li>
      ))}
    </ol>
  );
}
