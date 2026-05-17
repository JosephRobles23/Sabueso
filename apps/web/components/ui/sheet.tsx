"use client";

/**
 * Sheet — slide-in dialog. Mirrors the shadcn/ui `sheet` API but is built on
 * a small custom portal + focus-trap instead of `@radix-ui/react-dialog`.
 * (Turbopack in Next 16 currently fails to resolve a Radix-dialog transitive
 * peer dep in this worktree, so we self-implement to keep the build green.)
 */

import * as React from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

type Side = "right" | "left" | "top" | "bottom";

interface SheetContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
}

const SheetContext = React.createContext<SheetContextValue | null>(null);

export function Sheet({
  open,
  defaultOpen,
  onOpenChange,
  children,
}: {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}) {
  const isControlled = open !== undefined;
  const [internal, setInternal] = React.useState(defaultOpen ?? false);
  const value = isControlled ? open : internal;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (!isControlled) setInternal(next);
      onOpenChange?.(next);
    },
    [isControlled, onOpenChange],
  );

  return (
    <SheetContext.Provider value={{ open: value, setOpen }}>{children}</SheetContext.Provider>
  );
}

function useSheet() {
  const ctx = React.useContext(SheetContext);
  if (!ctx) throw new Error("Sheet primitives must be rendered inside <Sheet>");
  return ctx;
}

export function SheetTrigger({
  asChild: _asChild,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) {
  const { setOpen } = useSheet();
  return (
    <button type="button" onClick={() => setOpen(true)} {...props}>
      {children}
    </button>
  );
}

export function SheetClose({
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const { setOpen } = useSheet();
  return (
    <button
      type="button"
      onClick={(ev) => {
        props.onClick?.(ev);
        setOpen(false);
      }}
      {...props}
    >
      {children}
    </button>
  );
}

const SIDE_CLASSES: Record<Side, string> = {
  right: "right-0 top-0 h-full w-full sm:w-[420px] border-l",
  left: "left-0 top-0 h-full w-full sm:w-[420px] border-r",
  top: "top-0 left-0 w-full border-b",
  bottom: "bottom-0 left-0 w-full border-t",
};

const ENTER_TRANSFORM: Record<Side, string> = {
  right: "translate-x-full",
  left: "-translate-x-full",
  top: "-translate-y-full",
  bottom: "translate-y-full",
};

export interface SheetContentProps extends React.HTMLAttributes<HTMLDivElement> {
  side?: Side;
  hideCloseButton?: boolean;
}

export const SheetContent = React.forwardRef<HTMLDivElement, SheetContentProps>(
  ({ side = "right", className, children, hideCloseButton, ...props }, forwardedRef) => {
    const { open, setOpen } = useSheet();
    const localRef = React.useRef<HTMLDivElement | null>(null);
    const [mounted, setMounted] = React.useState(false);
    const [animateIn, setAnimateIn] = React.useState(false);

    // Sync ref forwarding.
    React.useImperativeHandle(forwardedRef, () => localRef.current as HTMLDivElement);

    // Mount portal target on the client only.
    React.useEffect(() => setMounted(true), []);

    // Esc handler + body scroll lock + autofocus.
    React.useEffect(() => {
      if (!open) return;
      const previouslyFocused = document.activeElement as HTMLElement | null;
      const onKey = (e: KeyboardEvent) => {
        if (e.key === "Escape") {
          e.preventDefault();
          setOpen(false);
        }
      };
      document.addEventListener("keydown", onKey);
      const prevOverflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";

      // Focus the panel after the next paint so the animation starts visually.
      requestAnimationFrame(() => {
        setAnimateIn(true);
        localRef.current?.focus();
      });

      return () => {
        document.removeEventListener("keydown", onKey);
        document.body.style.overflow = prevOverflow;
        previouslyFocused?.focus?.();
        setAnimateIn(false);
      };
    }, [open, setOpen]);

    if (!mounted || !open) return null;

    return createPortal(
      <div className="fixed inset-0 z-50">
        <div
          aria-hidden
          onClick={() => setOpen(false)}
          className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
          style={{ opacity: animateIn ? 1 : 0 }}
        />
        <div
          ref={localRef}
          role="dialog"
          aria-modal="true"
          tabIndex={-1}
          className={cn(
            "fixed flex flex-col gap-4 bg-[var(--color-surface)] p-5 shadow-xl outline-none",
            "border-[var(--color-border-default)]",
            "transition-transform duration-300 ease-out",
            SIDE_CLASSES[side],
            className,
          )}
          style={{
            transform: animateIn ? "translate(0,0)" : transformOf(side),
          }}
          {...props}
        >
          {children}
          {hideCloseButton ? null : (
            <button
              type="button"
              aria-label="Cerrar"
              onClick={() => setOpen(false)}
              className="absolute right-3 top-3 rounded-sm p-1 text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-surface-2)] hover:text-[var(--color-text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>,
      document.body,
    );

    function transformOf(s: Side): string {
      return ENTER_TRANSFORM[s].includes("-")
        ? `translate${ENTER_TRANSFORM[s].includes("y") ? "Y" : "X"}(-100%)`
        : `translate${ENTER_TRANSFORM[s].includes("y") ? "Y" : "X"}(100%)`;
    }
  },
);
SheetContent.displayName = "SheetContent";

export function SheetHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1.5 pr-8", className)} {...props} />;
}

export const SheetTitle = React.forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h2
      ref={ref}
      className={cn("font-display text-xl leading-tight tracking-tight", className)}
      {...props}
    />
  ),
);
SheetTitle.displayName = "SheetTitle";

export const SheetDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p
      ref={ref}
      className={cn("text-sm text-[var(--color-text-secondary)]", className)}
      {...props}
    />
  ),
);
SheetDescription.displayName = "SheetDescription";
