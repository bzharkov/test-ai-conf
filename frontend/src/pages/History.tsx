import { HistoryList } from "../components/HistoryList";

export function History() {
  return (
    <div className="max-w-3xl">
      <h1 className="mb-4 text-2xl font-semibold">История запросов</h1>
      <HistoryList />
    </div>
  );
}
