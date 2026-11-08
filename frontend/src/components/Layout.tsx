import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { useCompareIds } from "../lib/storage";

const navCls = ({ isActive }: { isActive: boolean }) =>
  `px-2 py-1 text-sm ${isActive ? "text-accent" : "text-mute hover:text-ink"}`;

export function Layout({ children }: { children: ReactNode }) {
  const compare = useCompareIds();
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-panel/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <Link to="/" className="font-mono text-sm font-semibold tracking-wider">
            PC<span className="text-accent">/</span>CONF
          </Link>
          <nav className="flex flex-wrap items-center gap-1">
            <NavLink to="/" end className={navCls}>
              Подбор
            </NavLink>
            <NavLink to="/history" className={navCls}>
              История
            </NavLink>
            <NavLink to={`/compare?ids=${compare.join(",")}`} className={navCls}>
              Сравнение{compare.length ? ` (${compare.length})` : ""}
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">{children}</main>
      <footer className="border-t border-line px-4 py-4 text-xs text-mute">
        <div className="mx-auto max-w-6xl space-y-1">
          <p>
            Характеристики комплектующих:{" "}
            <a
              className="underline hover:text-accent"
              href="https://github.com/buildcores/buildcores-open-db"
              target="_blank"
              rel="noreferrer"
            >
              BuildCores OpenDB
            </a>
            , лицензия{" "}
            <a
              className="underline hover:text-accent"
              href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
              target="_blank"
              rel="noreferrer"
            >
              CC BY-NC-SA 4.0
            </a>
            .
          </p>
          <p>
            В демо-режиме цены ориентировочные; источник и дата указаны у каждой цены. Учебный
            проект, не является торговой офертой.
          </p>
        </div>
      </footer>
    </div>
  );
}
