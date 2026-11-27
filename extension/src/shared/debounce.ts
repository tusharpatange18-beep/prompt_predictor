/**
 * Returns a version of `fn` that waits until the calls stop for `ms` milliseconds, then runs
 * once with the last arguments. Used so we ask the backend only after the user pauses typing.
 */
export function debounce<A extends unknown[]>(fn: (...args: A) => void, ms: number) {
  let timer: ReturnType<typeof setTimeout> | undefined;

  return function (...args: A) {
    clearTimeout(timer); // a new call cancels the one that was waiting
    timer = setTimeout(function () {
      fn(...args);
    }, ms);
  };
}
