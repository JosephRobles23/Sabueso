import { Nav } from "@/components/nav";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <Nav variant="app" />
      <div className="flex-1">{children}</div>
    </div>
  );
}
