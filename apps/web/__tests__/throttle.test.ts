import { beforeEach, describe, expect, it, vi } from "vitest";

import { throttle } from "@/lib/throttle";

describe("throttle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("invokes leading call immediately and coalesces bursts inside the window", () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 500);

    throttled("a");
    throttled("b");
    throttled("c");

    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenLastCalledWith("a");

    vi.advanceTimersByTime(499);
    expect(fn).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenLastCalledWith("c");
  });

  it("flush forces the pending call to fire", () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 500);

    throttled("first");
    throttled("second");
    expect(fn).toHaveBeenCalledTimes(1);

    throttled.flush();
    expect(fn).toHaveBeenCalledTimes(2);
    expect(fn).toHaveBeenLastCalledWith("second");
  });

  it("cancel drops the pending call", () => {
    const fn = vi.fn();
    const throttled = throttle(fn, 500);
    throttled("a");
    throttled("b");
    throttled.cancel();
    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(1);
  });
});
