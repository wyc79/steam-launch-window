// Which option of the tag list is highlighted (-1: none), apart from the DOM.

// when the list opens: the first option if something is typed, else none
export function openActive(typed, count) {
  return typed && count ? 0 : -1;
}

// after an arrow key (step 1 down, -1 up). A closed list opens first; if that
// already highlights an option, the key only opened it.
export function arrowActive({ open, active, typed, count }, step) {
  const start = open ? active : openActive(typed, count);
  if (!count) return -1;
  if (!open && start >= 0) return start;
  return start < 0 ? (step > 0 ? 0 : count - 1) : (start + step + count) % count;
}
