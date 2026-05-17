import { renderHook, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useLocalStorageInvestigation } from "@/hooks/useLocalStorageInvestigation";
import { initialInvestigationState } from "@/hooks/useInvestigation";

describe("useLocalStorageInvestigation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
  });

  it("throttles writes to localStorage at ~500ms", () => {
    const { result } = renderHook(() => useLocalStorageInvestigation("inv-1"));
    const setSpy = vi.spyOn(Storage.prototype, "setItem");

    act(() => {
      result.current.save?.(initialInvestigationState("inv-1"));
      result.current.save?.({ ...initialInvestigationState("inv-1"), progress: 10 });
      result.current.save?.({ ...initialInvestigationState("inv-1"), progress: 20 });
    });

    expect(setSpy).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(setSpy).toHaveBeenCalledTimes(2);
    const lastValue = JSON.parse(setSpy.mock.calls[1]![1] as string);
    expect(lastValue.progress).toBe(20);
  });

  it("hydrates from previously persisted state", () => {
    const seed = { ...initialInvestigationState("inv-2"), progress: 77 };
    window.localStorage.setItem("sabueso:investigation:inv-2", JSON.stringify(seed));

    const { result, rerender } = renderHook(() => useLocalStorageInvestigation("inv-2"));
    rerender();
    expect(result.current.hydrated?.progress).toBe(77);
  });
});
