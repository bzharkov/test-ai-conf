import type { components } from "./schema";

type S = components["schemas"];
type ReqRaw = S["Requirements"];
type PrefsRaw = NonNullable<ReqRaw["preferences"]>;
/** Responses always carry defaulted fields, so they are required here (OpenAPI marks them optional). */
export type Preferences = PrefsRaw &
  Required<
    Pick<
      PrefsRaw,
      | "cpu_brand"
      | "gpu_brand"
      | "form_factor"
      | "wifi_required"
      | "quiet"
      | "rgb"
      | "no_discrete_gpu"
    >
  >;
export type Requirements = ReqRaw & {
  use_cases: NonNullable<ReqRaw["use_cases"]>;
  primary_use_case: string;
  preferences: Preferences;
  budget_assumed: boolean;
  must_include: string[];
  exclude: string[];
};
export type BuildOut = S["BuildOut"];
export type BuildSummary = S["BuildSummary"];
export type ComponentOut = S["ComponentOut"];
export type ConfigureResponse = Omit<S["ConfigureResponse"], "requirements"> & {
  requirements: Requirements;
};
export type AlternativeOut = S["AlternativeOut"];
export type CompareResponse = S["CompareResponse"];
export type HistoryItem = S["HistoryItem"];
export type ChatMessageOut = S["ChatMessageOut"];
export type ReplaceResponse = S["ReplaceResponse"];
export type Warn = S["Warn"];
export type UseCase = NonNullable<ReqRaw["use_cases"]>[number];
export type Intent = "cheaper" | "better" | "similar";

export interface ConfigureFilters {
  budget_rub?: number;
  wifi?: boolean;
  compact?: boolean;
  cpu_brand?: "amd" | "intel";
  no_gpu?: boolean;
}
