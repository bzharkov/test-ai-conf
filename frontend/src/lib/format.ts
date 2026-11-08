export const rub = (n: number | null | undefined): string =>
  n == null ? "—" : `${Math.round(n).toLocaleString("ru-RU")} ₽`;

export const signedRub = (n: number): string =>
  `${n > 0 ? "+" : n < 0 ? "−" : ""}${rub(Math.abs(n))}`;

export const pct = (n: number | null | undefined): string =>
  n == null ? "нет данных" : `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(Math.round(n))}%`;

export const USE_CASE_RU: Record<string, string> = {
  gaming: "игры",
  office: "офис",
  video_editing: "видеомонтаж",
  "3d_render": "3D-рендер",
  programming: "программирование",
  study: "учёба",
  streaming: "стриминг",
  ml: "ML",
};

export const SPEC_LABELS: Record<string, string> = {
  socket: "Сокет",
  cores: "Ядра",
  threads: "Потоки",
  boost_clock_ghz: "Буст, ГГц",
  base_clock_ghz: "База, ГГц",
  tdp_w: "TDP, Вт",
  has_igpu: "iGPU",
  chipset: "Чипсет",
  form_factor: "Форм-фактор",
  memory_type: "Память",
  memory_slots: "Слотов",
  m2_slots: "M.2",
  wifi: "Wi-Fi",
  type: "Тип",
  capacity_gb_total: "Объём, ГБ",
  capacity_gb: "Объём, ГБ",
  modules: "Модулей",
  speed_mhz: "МГц",
  vram_gb: "VRAM, ГБ",
  length_mm: "Длина, мм",
  interface: "Интерфейс",
  height_mm: "Высота, мм",
  radiator_mm: "Радиатор, мм",
  wattage_w: "Мощность, Вт",
  efficiency: "Сертификат",
  modular: "Модульный",
  max_gpu_length_mm: "Макс. GPU, мм",
  max_cooler_height_mm: "Макс. кулер, мм",
};

const SHOW: Record<string, string[]> = {
  cpu: ["socket", "cores", "threads", "boost_clock_ghz", "tdp_w"],
  motherboard: ["socket", "chipset", "form_factor", "memory_type", "wifi"],
  ram: ["type", "capacity_gb_total", "speed_mhz"],
  gpu: ["chipset", "vram_gb", "length_mm", "tdp_w"],
  storage: ["type", "capacity_gb", "interface"],
  cpu_cooler: ["type", "height_mm", "radiator_mm"],
  psu: ["wattage_w", "efficiency", "modular"],
  case: ["max_gpu_length_mm", "max_cooler_height_mm"],
};

export function keySpecs(category: string, specs: Record<string, unknown>): string {
  return (SHOW[category] ?? [])
    .filter((k) => specs[k] != null)
    .map((k) => {
      const v = specs[k];
      const shown = v === true ? "да" : v === false ? "нет" : String(v);
      return `${SPEC_LABELS[k] ?? k}: ${shown}`;
    })
    .join(" · ");
}
