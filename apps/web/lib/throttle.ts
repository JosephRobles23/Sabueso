export interface ThrottledFn<T extends unknown[]> {
  (...args: T): void;
  flush(): void;
  cancel(): void;
}

export function throttle<T extends unknown[]>(
  fn: (...args: T) => void,
  waitMs: number,
): ThrottledFn<T> {
  let lastCall = 0;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let pendingArgs: T | null = null;

  function invoke(args: T) {
    lastCall = Date.now();
    pendingArgs = null;
    fn(...args);
  }

  function throttled(...args: T) {
    const now = Date.now();
    const remaining = waitMs - (now - lastCall);
    pendingArgs = args;

    if (remaining <= 0) {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
      invoke(args);
    } else if (!timer) {
      timer = setTimeout(() => {
        timer = null;
        if (pendingArgs) invoke(pendingArgs);
      }, remaining);
    }
  }

  throttled.flush = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    if (pendingArgs) invoke(pendingArgs);
  };

  throttled.cancel = () => {
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
    pendingArgs = null;
  };

  return throttled as ThrottledFn<T>;
}
